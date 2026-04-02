from django.db import models
from store.models import Product, ProductVariation
from accounts.models import Accounts

class Cart(models.Model):
    cart_id = models.CharField(max_length=250, unique=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.cart_id
    
class CartItem(models.Model):
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE, null=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    quantity = models.PositiveIntegerField(default=1)
    variation = models.ManyToManyField(ProductVariation, blank=True)
    is_active = models.BooleanField(default=True)

    def __unicode__(self):
        return self.product