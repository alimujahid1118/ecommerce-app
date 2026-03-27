from django.shortcuts import render, get_object_or_404
from django.template import loader
from django.http import HttpResponse
from .models import Product, ProductVariation
from category.models import Category
from carts.models import CartItem
from carts.views import _cart_id
from django.core.paginator import Paginator
from django.db.models import Q

def view_products(request, category_slug = None):
    template = loader.get_template("store/store.html")
    if category_slug is not None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories,is_available=True)
        paginator = Paginator(products, 3)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        count = products.count()
    else:
        products = Product.objects.filter(is_available=True)
        paginator = Paginator(products, 3)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        count = products.count()
    context = {
        'products': paged_products,
        'count': count
    }
    return HttpResponse(template.render(context, request))

def product(request, category_slug, slug):
    template = loader.get_template("store/product.html")
    product = get_object_or_404(Product, slug=slug, is_available=True)
    variations = ProductVariation.objects.filter(product=product, is_active=True)
    variation_list = {}
    for variation in variations:
        category = variation.variation_category
        value = variation.variation_value
        if category not in variation_list:
            variation_list[category] = []
        variation_list[category].append(value)
    in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=product).exists()
    context = {
        'product': product,
        'in_cart': in_cart,
        'variation_list': variation_list,
    }
    return HttpResponse(template.render(context, request))

def search(request):
    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            searched_items = Product.objects.order_by('-created_date').filter(Q(product_name__icontains=keyword) | Q(description__icontains=keyword))
            count = searched_items.count()
    context = {
        'products': searched_items,
        'count': count
    }
    return render(request , 'store/store.html', context)