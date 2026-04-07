from django.contrib import admin
from .models import Product, ProductVariation, Reviews

class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'price', 'stock', 'is_available')
    prepopulated_fields = {'slug' : ('product_name',)}

class ProductVariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'variation_category', 'variation_value', 'is_active')
    list_filter = ('product', 'variation_category', 'variation_value')
    list_editable = ('is_active',)

class ReviewsAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'review_title', 'created_date')
    list_filter = ('product', 'user')
    search_fields = ('review_title', 'review_text')
    class Meta:
        model: Reviews
        verbose_name_plural = "Reviews"

admin.site.register(Product, ProductAdmin)
admin.site.register(ProductVariation, ProductVariationAdmin)
admin.site.register(Reviews, ReviewsAdmin)