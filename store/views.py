from itertools import count

from django.shortcuts import render, get_object_or_404
from django.template import loader
from django.http import HttpResponse
from .models import Product
from category.models import Category


def view_products(request, category_slug = None):
    template = loader.get_template("store/store.html")
    if category_slug is not None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories,is_available=True)
        count = products.count()
    else:
        products = Product.objects.filter(is_available=True)
        count = products.count()
    context = {
        'products': products,
        'count': count
    }
    return HttpResponse(template.render(context, request))

def product(request, category_slug, slug):
    template = loader.get_template("store/product.html")
    product = get_object_or_404(Product, slug=slug, is_available=True)
    context = {
        'product': product
    }
    return HttpResponse(template.render(context, request))