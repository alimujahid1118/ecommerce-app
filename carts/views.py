from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template import loader
from .models import Cart, CartItem
from store.models import Product, ProductVariation

def cart_detail(request, product_total = 0, total = 0, quantity = 0, cart_items = None):
    template = loader.get_template('cart/cart_detail.html')
    try:
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

    cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))

    # Get cart items for this product
    cart_items = CartItem.objects.filter(product=product, cart=cart)
    existing_item = None

    for item in cart_items:
        existing_variations = list(item.variation.all())
        if set(existing_variations) == set(product_variations):
            existing_item = item
            break

    if existing_item:
        existing_item.quantity += 1
        existing_item.save()
    else:
        cart_item = CartItem.objects.create(
            product=product,
            quantity=1,
            cart=cart
        )
        if product_variations:
            cart_item.variation.set(product_variations)
        cart_item.save()

    return redirect('cart_detail')


def remove_from_cart(request, product_id):
    product = Product.objects.get(id=product_id)
    cart = Cart.objects.get(cart_id=_cart_id(request))
    product_variations = []

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

        cart_items = CartItem.objects.filter(product=product, cart=cart)
        item_to_decrement = None

        for item in cart_items:
            existing_variations = list(item.variation.all())
            if set(existing_variations) == set(product_variations):
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
    cart = Cart.objects.get(cart_id=_cart_id(request))
    product_variations = []

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

        cart_items = CartItem.objects.filter(product=product, cart=cart)
        item_to_remove = None

        for item in cart_items:
            existing_variations = list(item.variation.all())
            if set(existing_variations) == set(product_variations):
                item_to_remove = item
                break

        if item_to_remove:
            item_to_remove.delete()

    return redirect("cart_detail")