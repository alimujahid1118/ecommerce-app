from django.urls import path, include
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('', include('allauth.urls')), 
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('payment-methods/', views.saved_payment_methods, name='saved_payment_methods'),
    path(
        'payment-methods/<int:pk>/delete/',
        views.delete_saved_payment_method,
        name='delete_saved_payment_method',
    ),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.resetPassword, name='resetPassword'),
]