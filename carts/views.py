from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template import loader
from .models import Cart, CartItem
from store.models import Product, ProductVariation
from django.contrib.auth.decorators import login_required

def cart_detail(request, product_total = 0, total = 0, quantity = 0, cart_items = None):
    template = loader.get_template('cart/cart_detail.html')
    tax = 0
    grand_total = 0
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
            for cart_item in cart_items:
                total = total + (cart_item.product.price * cart_item.quantity)
                quantity = quantity + cart_item.quantity
                cart_item.product_total = cart_item.product.price * cart_item.quantity
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            for cart_item in cart_items:
                total = total + (cart_item.product.price * cart_item.quantity)
                quantity = quantity + cart_item.quantity
                cart_item.product_total = cart_item.product.price * cart_item.quantity
            
        tax = (2 * total)/100
        grand_total = total + tax
    except Cart.DoesNotExist:
        pass
    context = {
        'cart_items': cart_items,
        'total': total,
        'quantity': quantity,
        'tax': tax,
        'grand_total' : grand_total,
    }
    return HttpResponse(template.render(context, request))

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def add_to_cart(request, product_id):
    product = Product.objects.get(id=product_id)
    product_variations = []
    product_variation_ids = frozenset()

    # Get selected variations
    if request.method == "POST":
        for key, value in request.POST.items():
            if key == "csrfmiddlewaretoken":
                continue

            variation = ProductVariation.objects.filter(
                product=product,
                variation_category__iexact=key,
                variation_value__iexact=value
            ).first()

            if variation:
                product_variations.append(variation)
    product_variation_ids = frozenset(v.id for v in product_variations)

    # Decide cart owner (user or session cart)
    if request.user.is_authenticated:
        cart_filter = {"user": request.user}
    else:
        cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))
        cart_filter = {"cart": cart}

    # Find existing cart items
    cart_items = CartItem.objects.filter(
        product=product,
        is_active=True,
        **cart_filter
    )

    existing_item = None
    for item in cart_items:
        item_variation_ids = frozenset(item.variation.values_list('id', flat=True))
        if item_variation_ids == product_variation_ids:
            existing_item = item
            break

    # Update or create cart item
    if existing_item:
        existing_item.quantity += 1
        existing_item.save()
    else:
        cart_item = CartItem.objects.create(
            product=product,
            quantity=1,
            **cart_filter
        )
        if product_variations:
            cart_item.variation.set(product_variations)

    return redirect("cart_detail")


def remove_from_cart(request, product_id):
    product = Product.objects.get(id=product_id)
    product_variations = []
    product_variation_ids = frozenset()

    if request.method == 'POST':
        for key, value in request.POST.items():
            if key != 'csrfmiddlewaretoken':
                variation = ProductVariation.objects.filter(
                    product=product,
                    variation_category__iexact=key,
                    variation_value__iexact=value
                ).first()
                if variation:
                    product_variations.append(variation)
        product_variation_ids = frozenset(v.id for v in product_variations)

        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(
                user=request.user,
                product=product,
                is_active=True,
            )
        else:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
            except Cart.DoesNotExist:
                return redirect('cart_detail')
            cart_items = CartItem.objects.filter(product=product, cart=cart)
        item_to_decrement = None

        for item in cart_items:
            item_variation_ids = frozenset(item.variation.values_list('id', flat=True))
            if item_variation_ids == product_variation_ids:
                item_to_decrement = item
                break

        if item_to_decrement:
            if item_to_decrement.quantity > 1:
                item_to_decrement.quantity -= 1
                item_to_decrement.save()
            else:
                item_to_decrement.delete()

    return redirect('cart_detail')


def remove_cart_item(request, product_id):
    product = Product.objects.get(id=product_id)
    product_variations = []
    product_variation_ids = frozenset()

    if request.method == 'POST':
        for key, value in request.POST.items():
            if key != 'csrfmiddlewaretoken':
                variation = ProductVariation.objects.filter(
                    product=product,
                    variation_category__iexact=key,
                    variation_value__iexact=value
                ).first()
                if variation:
                    product_variations.append(variation)
        product_variation_ids = frozenset(v.id for v in product_variations)
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, product=product, is_active=True)
        else:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
            except Cart.DoesNotExist:
                return redirect("cart_detail")
            cart_items = CartItem.objects.filter(product=product, cart=cart)
        item_to_remove = None

        for item in cart_items:
            item_variation_ids = frozenset(item.variation.values_list('id', flat=True))
            if item_variation_ids == product_variation_ids:
                item_to_remove = item
                break

        if item_to_remove:
            item_to_remove.delete()

    return redirect("cart_detail")

@login_required
def checkout(request, product_total = 0, total = 0, quantity = 0, cart_items = None):
    tax = 0
    grand_total = 0
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        for cart_item in cart_items:
            total = total + (cart_item.product.price * cart_item.quantity)
            quantity = quantity + cart_item.quantity
            cart_item.product_total = cart_item.product.price * cart_item.quantity
            
        tax = (2 * total)/100
        grand_total = total + tax
    except Cart.DoesNotExist:
        pass
    context = {
        'cart_items': cart_items,
        'total': total,
        'quantity': quantity,
        'tax': tax,
        'grand_total' : grand_total,
    }
    return render(request, 'cart/checkout.html', context)