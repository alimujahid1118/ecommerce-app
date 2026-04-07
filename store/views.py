from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse
from .models import Product, ProductVariation, Reviews
from category.models import Category
from carts.models import CartItem
from carts.views import _cart_id
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.models import Accounts
from orders.models import Order

from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator


def view_products(request, category_slug=None):

    # ----- BASE QUERY -----
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(
            category=category,
            is_available=True
        )
    else:
        products = Product.objects.filter(is_available=True)

    # ======================
    # SIZE FILTER
    # ======================
    sizes = request.GET.getlist('size')

    if sizes:
        size_query = Q()
        for size in sizes:
            size_query |= Q(
                productvariation__variation_category__iexact='size',
                productvariation__variation_value__iexact=size
            )

        products = products.filter(size_query).distinct()

    # ======================
    # PRICE FILTER
    # ======================
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    # convert safely to numbers
    try:
        if min_price:
            products = products.filter(price__gte=float(min_price))

        if max_price:
            products = products.filter(price__lte=float(max_price))

    except ValueError:
        pass  # ignore invalid input

    # ======================
    # PAGINATION
    # ======================
    paginator = Paginator(products, 3)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)

    context = {
        'products': paged_products,
        'count': products.count(),
    }

    return render(request, "store/store.html", context)

def product(request, category_slug, slug):
    template = loader.get_template("store/product.html")
    product = get_object_or_404(Product, slug=slug, is_available=True)
    # Get the reviews of product
    reviews = Reviews.objects.filter(product=product)
    user = Reviews.objects.filter(product=product, user=request.user.email).exists() if request.user.is_authenticated else False
    review_user = Accounts.objects.filter(email=request.user.email).first() if request.user.is_authenticated else None
    if request.method == 'POST':
        review_title = request.POST.get('review_title')
        review_text = request.POST.get('review_text')
        if review_title and review_text and request.user.is_authenticated:
            Reviews.objects.create(
                product=product,
                user=request.user.email,
                review_title=review_title,
                review_text=review_text
                
            )
            return redirect('product', category_slug=category_slug, slug=slug)
        
    #Check if user has ordered or not
    has_user_ordered = Order.objects.filter(user=request.user, orderproduct__product=product, status='completed').exists() if request.user.is_authenticated else False

    # Get active variations for the product
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
        'reviews': reviews,
        'variation_list': variation_list,
        'review_user': review_user,
        'has_user_ordered': has_user_ordered,
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