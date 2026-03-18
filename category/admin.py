from django.contrib import admin
from .models import Category

class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)

admin.site.register(Category, CategoryAdmin)