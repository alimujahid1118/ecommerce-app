from django.urls import path
from . import views

urlpatterns = [
    path('', views.view_products, name='view_products'),
    path('category/<slug:category_slug>/', views.view_products, name='products_by_category'),
    path('category/<slug:category_slug>/<slug:slug>/', views.product, name='product'),
    path('search/', views.search, name='search'),
]