from .models import Cart, CartItem
from .views import _cart_id

def cart_total(request, total_quantity = 0):
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        for cart_item in cart_items:
            total_quantity = total_quantity + cart_item.quantity
    except Cart.DoesNotExist:
        pass
    return {'total_quantity': total_quantity}