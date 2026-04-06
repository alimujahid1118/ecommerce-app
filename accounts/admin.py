from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Accounts, SavedPaymentMethod

class AccountAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'phone_no', 'is_active')
    list_display_links = ('email', 'username', 'first_name')
    readonly_fields = ('date_joined', 'last_login')
    ordering = ('-date_joined',)

    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

admin.site.register(Accounts, AccountAdmin)


@admin.register(SavedPaymentMethod)
class SavedPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("user", "method_type", "label", "is_default", "created_at")
    list_filter = ("method_type", "is_default")
    search_fields = ("user__email", "label", "jazzcash_phone", "card_last_four")