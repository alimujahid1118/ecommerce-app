from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)


class MyAccountManager(BaseUserManager):

    def create_user(self, email, username, first_name, last_name, password=None):
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(
            email=self.normalize_email(email),
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, first_name, last_name, password):
        user = self.create_user(
            email,
            username,
            first_name,
            last_name,
            password,
        )

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save(using=self._db)
        return user


class Accounts(AbstractBaseUser, PermissionsMixin):

    username = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_no = models.CharField(max_length=15, blank=True, null=True)

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = MyAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email

    class Meta:
        verbose_name_plural = 'Accounts'
        ordering = ['-date_joined']


class SavedPaymentMethod(models.Model):
    """User-saved JazzCash or card metadata (never store full card numbers)."""

    METHOD_JAZZCASH = "jazzcash"
    METHOD_DEBIT_CARD = "debit_card"
    METHOD_CHOICES = (
        (METHOD_JAZZCASH, "JazzCash"),
        (METHOD_DEBIT_CARD, "Bank debit card"),
    )

    user = models.ForeignKey(
        Accounts,
        on_delete=models.CASCADE,
        related_name="saved_payment_methods",
    )
    method_type = models.CharField(max_length=20, choices=METHOD_CHOICES)
    label = models.CharField(max_length=120, blank=True)
    is_default = models.BooleanField(default=False)

    jazzcash_phone = models.CharField(max_length=20, blank=True)

    card_last_four = models.CharField(max_length=4, blank=True)
    cardholder_name = models.CharField(max_length=120, blank=True)
    card_exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        if self.method_type == self.METHOD_JAZZCASH:
            return f"JazzCash {self.jazzcash_phone or self.label or self.pk}"
        return f"Card •••• {self.card_last_four}" if self.card_last_four else f"Card {self.pk}"

    def display_name(self):
        if self.label:
            return self.label
        if self.method_type == self.METHOD_JAZZCASH:
            return f"JazzCash {self.jazzcash_phone}"
        return f"Debit card •••• {self.card_last_four}"