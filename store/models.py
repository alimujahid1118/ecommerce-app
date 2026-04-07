from django.db import models
from category.models import Category
from django.utils.text import slugify

class Product(models.Model):
    product_name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(max_length=500, blank=True)
    price = models.IntegerField()
    images = models.ImageField(upload_to='photos/products')
    stock = models.IntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.product_name)
        super().save(*args, **kwargs)

class ProductVariation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation_category = models.CharField(max_length=100, choices=(('color', 'color'), ('size', 'size'), ('material', 'material')))
    variation_value = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.variation_value
    
class Reviews(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.CharField(max_length=100)
    review_title = models.CharField(max_length=200)
    review_text = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user} on {self.product.product_name}"