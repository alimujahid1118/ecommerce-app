from django.urls import path, include
from . import views

urlpatterns = [
    path('place-order/', views.place_order, name='place_order'),
    path('pay/<int:order_id>/', views.pay_order, name='pay_order'),
    path('payment/', views.payment, name='payment'),
    path('jazzcash/return/', views.jazzcash_return, name='jazzcash_return'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path(
        'my-orders/<int:order_id>/change-details/',
        views.edit_order_details,
        name='edit_order_details',
    ),
] 