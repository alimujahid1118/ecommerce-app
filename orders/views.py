import uuid
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from accounts.models import SavedPaymentMethod
from carts.models import CartItem

from . import jazzcash
from .forms import CheckoutPaymentForm, OrderForm
from .models import Order, OrderProduct, Payment


def _payment_page_context(request, order, payment_form=None):
    """Context for payment.html: order, line items, optional Payment, totals, form."""
    order_products = list(
        OrderProduct.objects.filter(order=order).select_related("product")
    )
    for op in order_products:
        op.line_total = op.product_price * op.quantity
    subtotal = order.order_total - order.tax
    if payment_form is None:
        payment_form = CheckoutPaymentForm(user=request.user)
    return {
        "order": order,
        "order_products": order_products,
        "payment": order.payment,
        "total": subtotal,
        "tax": order.tax,
        "grand_total": order.order_total,
        "payment_form": payment_form,
        "has_saved_methods": SavedPaymentMethod.objects.filter(user=request.user).exists(),
        "jazzcash_gateway": jazzcash.is_configured(),
    }


def _create_saved_from_checkout(user, cleaned):
    """Persist JazzCash or masked card metadata after checkout (optional)."""
    if not cleaned.get("save_payment_method"):
        return
    if cleaned.get("saved_method"):
        return
    pm = cleaned.get("payment_method")
    has_any = SavedPaymentMethod.objects.filter(user=user).exists()
    if pm == "jazzcash":
        phone = cleaned.get("jazzcash_phone", "").strip()
        if not phone:
            return
        if SavedPaymentMethod.objects.filter(
            user=user,
            method_type=SavedPaymentMethod.METHOD_JAZZCASH,
            jazzcash_phone=phone,
        ).exists():
            return
        SavedPaymentMethod.objects.create(
            user=user,
            method_type=SavedPaymentMethod.METHOD_JAZZCASH,
            jazzcash_phone=phone,
            label=f"JazzCash {phone}",
            is_default=not has_any,
        )
    elif pm == "debit_card":
        digits = cleaned.get("card_number_digits", "")
        if len(digits) < 12:
            return
        SavedPaymentMethod.objects.create(
            user=user,
            method_type=SavedPaymentMethod.METHOD_DEBIT_CARD,
            card_last_four=digits[-4:],
            cardholder_name=cleaned["cardholder_name"].strip(),
            card_exp_month=cleaned["card_exp_month"],
            card_exp_year=cleaned["card_exp_year"],
            label=f"Debit card •••• {digits[-4:]}",
            is_default=not has_any,
        )


def _payment_method_label(cleaned):
    saved = cleaned.get("saved_method")
    if saved:
        return (
            "JazzCash"
            if saved.method_type == SavedPaymentMethod.METHOD_JAZZCASH
            else "Bank debit card"
        )
    if cleaned.get("payment_method") == "jazzcash":
        return "JazzCash"
    return "Bank debit card"


def _order_can_pay(order):
    """Unpaid orders in New status can be paid (including later from My orders)."""
    if order.payment_id:
        return False
    if order.status == "Cancelled":
        return False
    return order.status == "New"


def _finalize_order_payment(order, user, payment_method_label, payment_id=None):
    """Persist Payment and mark order Accepted (used by simulator and JazzCash return)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_id:
            return False
        pid = (payment_id or f"PAY-{uuid.uuid4().hex[:14].upper()}")[:100]
        payment = Payment.objects.create(
            user=user,
            payment_id=pid,
            payment_method=payment_method_label[:100],
            amount_paid=str(order.order_total),
            status="Completed",
        )
        order.payment = payment
        order.status = "Accepted"
        order.save(update_fields=["payment", "status", "updated_at"])
        OrderProduct.objects.filter(order=order).update(payment=payment)
    return True


def _complete_order_payment(request, order, form):
    """Create Payment row, link order and line items, optionally save payment method."""
    cleaned = form.cleaned_data
    if not _finalize_order_payment(order, request.user, _payment_method_label(cleaned)):
        return False
    _create_saved_from_checkout(request.user, cleaned)
    return True


def _should_redirect_jazzcash_gateway(cleaned):
    if not jazzcash.is_configured():
        return False
    saved = cleaned.get("saved_method")
    if saved:
        return saved.method_type == SavedPaymentMethod.METHOD_JAZZCASH
    return cleaned.get("payment_method") == "jazzcash"


def _jazzcash_mobile_from_cleaned(cleaned):
    saved = cleaned.get("saved_method")
    if saved and saved.method_type == SavedPaymentMethod.METHOD_JAZZCASH:
        return (saved.jazzcash_phone or "").replace(" ", "").strip()
    return (cleaned.get("jazzcash_phone") or "").replace(" ", "").strip()


def _redirect_to_jazzcash_hosted(request, order, cleaned):
    mobile = _jazzcash_mobile_from_cleaned(cleaned)
    if len(mobile) < 10:
        messages.error(request, "Enter a valid JazzCash mobile number.")
        return None
    return_url = request.build_absolute_uri(reverse("jazzcash_return"))
    post_url, fields = jazzcash.build_checkout_payload(
        order=order,
        mobile_number=mobile,
        return_url=return_url,
    )
    request.session["jazzcash_pending"] = {
        "order_id": order.pk,
        "txn_ref": fields["pp_TxnRefNo"],
        "amount": fields["pp_Amount"],
        "user_id": request.user.pk,
    }
    return render(
        request,
        "orders/jazzcash_redirect.html",
        {"post_url": post_url, "fields": fields},
    )


def _cart_totals_for_user(user):
    """Same pricing rules as carts.views.checkout."""
    cart_items = CartItem.objects.filter(user=user, is_active=True).select_related("product")
    total = 0
    quantity = 0
    for item in cart_items:
        line = item.product.price * item.quantity
        total += line
        quantity += item.quantity
        item.product_total = line
    tax = (2 * total) / 100
    grand_total = total + tax
    return cart_items, total, quantity, tax, grand_total


@login_required
def place_order(request):
    cart_items, total, quantity, tax, grand_total = _cart_totals_for_user(request.user)
    order_number = f"ORDER{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if request.method == "POST":
        if not cart_items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect("checkout")

        form = OrderForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                lines = list(
                    CartItem.objects.filter(user=request.user, is_active=True).select_related(
                        "product"
                    )
                )
                if not lines:
                    messages.warning(request, "Your cart is empty.")
                    return redirect("checkout")

                save_total = sum(c.product.price * c.quantity for c in lines)
                save_tax = (2 * save_total) / 100
                save_grand = save_total + save_tax

                order = form.save(commit=False)
                order.user = request.user
                order.order_number = order_number
                order.order_total = save_grand
                order.tax = save_tax
                order.status = "New"
                order.ip = request.META.get("REMOTE_ADDR", "")
                order.is_ordered = True
                order.save()

                for cart_item in lines:
                    OrderProduct.objects.create(
                        order=order,
                        user=request.user,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        product_price=cart_item.product.price,
                        ordered=True,
                    )

                CartItem.objects.filter(
                    pk__in=[c.pk for c in lines], user=request.user
                ).delete()

            request.session["checkout_order_id"] = order.pk

            messages.success(request, "Order placed successfully")
            context = _payment_page_context(request, order)
            return render(request, "orders/payment.html", context)

        messages.error(request, "Please correct the billing details and try again.")
        for field_name, errors in form.errors.items():
            label = form.fields.get(field_name).label if field_name in form.fields else None
            prefix = label or "Error"
            for err in errors:
                messages.error(request, f"{prefix}: {err}")
        context = {
            "form": form,
            "cart_items": cart_items,
            "total": total,
            "quantity": quantity,
            "tax": tax,
            "grand_total": grand_total,
        }
        return render(request, "cart/checkout.html", context)

    return redirect("checkout")


@login_required
def pay_order(request, order_id):
    """Start checkout payment for an existing unpaid order (e.g. skipped payment earlier)."""
    order = get_object_or_404(
        Order.objects.select_related("payment"),
        pk=order_id,
        user=request.user,
        is_ordered=True,
    )
    if order.payment_id:
        messages.info(request, "This order is already paid.")
        return redirect("my_orders")
    if not _order_can_pay(order):
        messages.warning(request, "This order cannot be paid online.")
        return redirect("my_orders")

    request.session["checkout_order_id"] = order.pk
    return redirect("payment")


@login_required
def payment(request):
    order_id = request.session.get("checkout_order_id")
    if not order_id:
        messages.warning(
            request,
            "No order selected for payment. Open an unpaid order from My orders and choose Pay now.",
        )
        return redirect("my_orders")

    order = (
        Order.objects.filter(pk=order_id, user=request.user)
        .select_related("payment")
        .first()
    )
    if not order:
        request.session.pop("checkout_order_id", None)
        messages.warning(request, "Order not found.")
        return redirect("my_orders")

    if order.payment_id:
        messages.info(request, "This order is already paid.")
        context = _payment_page_context(request, order)
        return render(request, "orders/payment.html", context)

    if request.method == "POST":
        form = CheckoutPaymentForm(request.POST, user=request.user)
        if form.is_valid():
            cleaned = form.cleaned_data
            if _should_redirect_jazzcash_gateway(cleaned):
                jc_resp = _redirect_to_jazzcash_hosted(request, order, cleaned)
                if jc_resp is not None:
                    return jc_resp
                context = _payment_page_context(request, order, payment_form=form)
                return render(request, "orders/payment.html", context)
            if not _complete_order_payment(request, order, form):
                request.session.pop("checkout_order_id", None)
                messages.info(request, "This order was already paid.")
                return redirect("my_orders")
            request.session.pop("checkout_order_id", None)
            messages.success(request, "Payment completed successfully.")
            return redirect("my_orders")
        context = _payment_page_context(request, order, payment_form=form)
        return render(request, "orders/payment.html", context)

    context = _payment_page_context(request, order)
    return render(request, "orders/payment.html", context)

@csrf_exempt
def jazzcash_return(request):
    """
    JazzCash POSTs payment result here. CSRF exempt — external gateway callback.
    """
    if request.method != "POST":
        return redirect("home")

    pending = request.session.get("jazzcash_pending")
    txn_ref = request.POST.get("pp_TxnRefNo", "")
    bill_ref = request.POST.get("pp_BillReference", "")
    code = request.POST.get("pp_ResponseCode") or request.POST.get("responseCode", "")

    if not pending:
        messages.error(request, "Payment session expired or invalid.")
        return redirect("my_orders")

    if not request.user.is_authenticated:
        from django.contrib.auth import get_user_model
        from django.contrib.auth import login as auth_login

        uid = pending.get("user_id")
        if not uid:
            messages.error(request, "Invalid payment session.")
            return redirect("login")
        user = get_user_model().objects.filter(pk=uid).first()
        if not user:
            messages.error(request, "Invalid payment session.")
            return redirect("login")
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    if request.user.pk != pending.get("user_id"):
        messages.error(request, "Session does not match this payment.")
        return redirect("my_orders")

    try:
        order_id = int(bill_ref)
    except ValueError:
        order_id = 0
    if order_id != pending.get("order_id"):
        messages.error(request, "Order mismatch.")
        return redirect("my_orders")

    order = Order.objects.filter(pk=order_id, user=request.user).first()
    if not order:
        messages.error(request, "Order not found.")
        return redirect("my_orders")

    if str(pending.get("amount")) != str(request.POST.get("pp_Amount", "")):
        messages.error(request, "Amount mismatch.")
        return redirect("my_orders")

    if txn_ref != pending.get("txn_ref"):
        messages.error(request, "Transaction reference mismatch.")
        return redirect("my_orders")

    if order.payment_id:
        request.session.pop("jazzcash_pending", None)
        messages.info(request, "This order was already paid.")
        return redirect("my_orders")

    request.session["checkout_order_id"] = order.pk

    if code == "000":
        ref = request.POST.get("pp_RetreivalReferenceNo") or txn_ref
        _finalize_order_payment(
            order,
            request.user,
            "JazzCash (gateway)",
            payment_id=str(ref),
        )
        request.session.pop("jazzcash_pending", None)
        request.session.pop("checkout_order_id", None)
        messages.success(request, "JazzCash payment completed.")
        return redirect("my_orders")

    err = (
        request.POST.get("pp_ResponseMessage")
        or request.POST.get("responseMessage")
        or "Payment was not completed"
    )
    messages.error(request, err)
    return redirect("payment")


@login_required
def my_orders(request):
    orders = (
        Order.objects.filter(user=request.user, is_ordered=True)
        .select_related("payment")
        .annotate(
            item_count=Count("orderproduct"),
            subtotal=F("order_total") - F("tax"),
        )
        .order_by("-created_at")
    )
    return render(request, "orders/my_orders.html", {"orders": orders})


EDITABLE_ORDER_STATUSES = frozenset({"New"})


@login_required
def edit_order_details(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user, is_ordered=True)
    if order.status not in EDITABLE_ORDER_STATUSES:
        messages.error(
            request,
            "This order can no longer be edited. Contact support if you need help.",
        )
        return redirect("my_orders")

    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, "Order details updated successfully.")
            return redirect("my_orders")
    else:
        form = OrderForm(instance=order)

    return render(
        request,
        "orders/edit_order_details.html",
        {"form": form, "order": order},
    )