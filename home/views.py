from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from store.models import Product

def home(request):
    template = loader.get_template("home.html")
    products = Product.objects.filter(is_available=True)
    context = {
        'products': products
    }
    return HttpResponse(template.render(context, request))