from urllib.parse import urlparse, urlencode

from .models import Accounts, SavedPaymentMethod
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, Resolver404, reverse
from .forms import (
    LoginForm,
    RegistrationForm,
    SavedPaymentMethodForm,
    UserProfileForm,
)
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from carts.models import Cart, CartItem
from carts.views import _cart_id
from orders.models import Order


def _safe_checkout_next_url(request):
    """If next points at checkout, return canonical checkout URL; else None."""
    raw = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if not raw:
        return None
    if raw.startswith('//'):
        return None
    if '://' in raw:
        path = urlparse(raw).path or '/'
    else:
        if not raw.startswith('/'):
            return None
        path = raw.split('?')[0]
    try:
        match = resolve(path)
    except Resolver404:
        return None
    if match.url_name != 'checkout':
        return None
    return reverse('checkout')

#Verification Email
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    else:
        if request.method == 'POST':
            form = RegistrationForm(request.POST)

            if form.is_valid():
                email = form.cleaned_data.get('email')

                if Accounts.objects.filter(email=email).exists():
                    messages.error(request, 'Email already exists.')
                    return redirect('register')
                
                user = form.save(commit=False)

                # Generate unique username
                base_username = user.email.split('@')[0]
                username = base_username
                counter = 1
                while Accounts.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

                # Create user safely
                user = Accounts.objects.create_user(
                    email=user.email,
                    username=username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    password=form.cleaned_data.get('password')
                )
                user.phone_no = form.cleaned_data.get('phone_no')
                user.is_active = False
                user.save()

                # Send activation email
                current_site = get_current_site(request)
                scheme = "https" if request.is_secure() else "http"
                message = render_to_string(
                    'accounts/activation_email.html',
                    {
                        'user': user,
                        'domain': current_site.domain,
                        'scheme': scheme,
                        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                        'token': default_token_generator.make_token(user)
                    }
                )
                email_msg = EmailMessage(
                    'Activate your account',
                    message,
                    to=[user.email]
                )
                email_msg.send()

                # Registration success → redirect to login with ?command=verification
                return redirect(f"/accounts/login/?command=verification&email={user.email}")

        else:
            form = RegistrationForm()

        return render(request, 'accounts/register.html', {'form': form})

def login(request):

    if request.user.is_authenticated:
        return redirect('home')
    else:
        next_param = request.GET.get('next', '') or request.POST.get('next', '')
        if request.method == 'POST':
            form = LoginForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data.get('email')
                password = form.cleaned_data.get('password')
                user = authenticate(request, username=email, password=password)
                if user is not None:
                    try:
                        # Merge the current anonymous cart into the user's cart.
                        # This prevents duplicates when a user:
                        # 1) adds items while logged out
                        # 2) logs in (items get assigned to the user)
                        # 3) logs out and adds the same items again
                        # 4) logs back in (we must increment quantity instead of adding a new row)
                        session_cart_id = request.session.session_key
                        if session_cart_id:
                            cart = Cart.objects.get(cart_id=session_cart_id)
                            session_cart_items = CartItem.objects.filter(cart=cart, is_active=True)

                            for session_item in session_cart_items:
                                session_variation_ids = frozenset(
                                    session_item.variation.values_list('id', flat=True)
                                )

                                # Find user's existing items with the same product + exact variation set.
                                # If duplicates exist (from previous buggy logins), consolidate them into the first match.
                                user_matches = []
                                user_items = CartItem.objects.filter(
                                    user=user,
                                    product=session_item.product,
                                    is_active=True,
                                )
                                for existing in user_items:
                                    existing_variation_ids = frozenset(
                                        existing.variation.values_list('id', flat=True)
                                    )
                                    if existing_variation_ids == session_variation_ids:
                                        user_matches.append(existing)

                                if user_matches:
                                    user_match = user_matches[0]
                                    for dup in user_matches[1:]:
                                        user_match.quantity += dup.quantity
                                        dup.delete()

                                    user_match.quantity += session_item.quantity
                                    # Keep the merged quantity tied to the *current* session cart.
                                    user_match.cart = cart
                                    user_match.save(update_fields=['quantity', 'cart'])
                                    session_item.delete()
                                else:
                                    session_item.user = user
                                    session_item.save(update_fields=['user'])
                    except:
                        pass
                    auth_login(request, user)
                    messages.success(request, f'Welcome {user.first_name}!')
                    checkout_next = _safe_checkout_next_url(request)
                    if checkout_next:
                        return redirect(checkout_next)
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Invalid email or password.')
                    if next_param:
                        return redirect(f"{reverse('login')}?{urlencode({'next': next_param})}")
                    return redirect('login')
                    
        else:
            form = LoginForm()

        context = {
            'form': form,
            'next': next_param,
        }
        return render(request, 'accounts/login.html', context)

@login_required
def logout(request):
    auth_logout(request)
    return redirect('home')

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Accounts._default_manager.get(pk=uid)
    except (ValueError, OverflowError, TypeError, Accounts.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Congratulations! Your account is activated.')
        return redirect('login')
    else:
        messages.error(request, 'Invalid activation link.')
        return redirect('register')
    
@login_required
def dashboard(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True)
    total_orders = orders.count()
    total_spent = orders.aggregate(s=Sum("order_total"))["s"] or 0
    recent_orders = (
        orders.select_related("payment").order_by("-created_at")[:5]
    )
    unpaid_orders_count = Order.objects.filter(
        user=request.user,
        is_ordered=True,
        status="New",
        payment__isnull=True,
    ).count()
    context = {
        "orders": orders,
        "total_orders": total_orders,
        "total_spent": total_spent,
        "recent_orders": recent_orders,
        "unpaid_orders_count": unpaid_orders_count,
    }
    return render(request, "dashboard/dashboard.html", context)


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("edit_profile")
    else:
        form = UserProfileForm(instance=request.user)

    return render(
        request,
        "dashboard/edit_profile.html",
        {"form": form},
    )


@login_required
def saved_payment_methods(request):
    methods = SavedPaymentMethod.objects.filter(user=request.user)
    unpaid_orders_count = Order.objects.filter(
        user=request.user,
        is_ordered=True,
        status="New",
        payment__isnull=True,
    ).count()
    if request.method == "POST":
        form = SavedPaymentMethodForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Payment method saved.")
            return redirect("saved_payment_methods")
    else:
        form = SavedPaymentMethodForm(user=request.user)
    return render(
        request,
        "dashboard/saved_payment_methods.html",
        {
            "methods": methods,
            "form": form,
            "unpaid_orders_count": unpaid_orders_count,
        },
    )


@login_required
def delete_saved_payment_method(request, pk):
    obj = get_object_or_404(SavedPaymentMethod, pk=pk, user=request.user)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Payment method removed.")
    return redirect("saved_payment_methods")


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if Accounts.objects.filter(email=email).exists():
            user = Accounts.objects.get(email=email)

            # Send password reset email
            current_site = get_current_site(request)
            scheme = "https" if request.is_secure() else "http"
            message = render_to_string(
                'accounts/password_reset_email.html',
                {
                    'user': user,
                    'domain': current_site.domain,
                    'scheme': scheme,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user)
                }
            )
            email_msg = EmailMessage(
                'Reset your password',
                message,
                to=[user.email]
            )
            email_msg.send()

            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('login')
        else:
            messages.error(request, 'No account found with that email address.')
            return redirect('forgot_password')
    return render(request, 'accounts/forgot_password.html')

def password_reset_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Accounts._default_manager.get(pk=uid)
    except (ValueError, OverflowError, TypeError, Accounts.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid']  = uid
        messages.success(request, 'Please reset your password.')
        return redirect('resetPassword')
    else:
        messages.error(request, 'Invalid password reset link.')
        return redirect('forgot_password')

def resetPassword(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('resetPassword')

        uid = request.session.get('uid')
        if uid is None:
            messages.error(request, 'Session expired. Please try the password reset process again.')
            return redirect('forgot_password')

        try:
            user = Accounts._default_manager.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, 'Your password has been reset successfully. You can now log in with your new password.')
            return redirect('login')
        except Accounts.DoesNotExist:
            messages.error(request, 'User does not exist.')
            return redirect('forgot_password')
    return render(request, 'accounts/reset_password.html')