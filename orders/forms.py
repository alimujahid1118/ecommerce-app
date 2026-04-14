from django import forms

from accounts.models import SavedPaymentMethod

from .models import Order


class OrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This field is optional in checkout UI, so keep backend validation aligned.
        self.fields["address_line_2"].required = False

    class Meta:
        model = Order
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "address_line_1",
            "address_line_2",
            "country",
            "state",
            "city",
            "order_note",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"placeholder": "Enter First Name", "class": "form-control"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Enter Last Name", "class": "form-control"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "Enter Email", "class": "form-control"}
            ),
            "phone": forms.TextInput(
                attrs={"placeholder": "Enter Phone Number", "class": "form-control"}
            ),
            "address_line_1": forms.TextInput(
                attrs={"placeholder": "Enter Address Line 1", "class": "form-control"}
            ),
            "address_line_2": forms.TextInput(
                attrs={"placeholder": "Enter Address Line 2", "class": "form-control"}
            ),
            "country": forms.TextInput(
                attrs={"placeholder": "Enter Country", "class": "form-control"}
            ),
            "state": forms.TextInput(
                attrs={"placeholder": "Enter State", "class": "form-control"}
            ),
            "city": forms.TextInput(
                attrs={"placeholder": "Enter City", "class": "form-control"}
            ),
            "order_note": forms.Textarea(
                attrs={"placeholder": "Enter Order Note", "class": "form-control"}
            ),
        }


class CheckoutPaymentForm(forms.Form):
    PAYMENT_METHOD_CHOICES = (
        ("jazzcash", "JazzCash"),
        ("debit_card", "Bank debit card"),
    )

    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.RadioSelect(attrs={"class": "payment-method-radio"}),
        initial="jazzcash",
    )
    saved_method = forms.ModelChoiceField(
        queryset=SavedPaymentMethod.objects.none(),
        required=False,
        empty_label="Enter new payment details",
        widget=forms.Select(attrs={"class": "form-control", "id": "id_saved_method"}),
    )
    jazzcash_phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "03XX XXXXXXX",
                "autocomplete": "tel",
            }
        ),
    )
    card_number = forms.CharField(
        required=False,
        max_length=23,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Card number",
                "autocomplete": "cc-number",
            }
        ),
    )
    cardholder_name = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Name on card",
                "autocomplete": "cc-name",
            }
        ),
    )
    card_exp_month = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "MM"}),
    )
    card_exp_year = forms.IntegerField(
        required=False,
        min_value=2020,
        max_value=2100,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "YYYY"}),
    )
    card_cvv = forms.CharField(
        required=False,
        max_length=4,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"class": "form-control", "placeholder": "CVV", "autocomplete": "cc-csc"},
        ),
    )
    save_payment_method = forms.BooleanField(
        required=False,
        initial=False,
        label="Save this payment method for next time",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["saved_method"].queryset = SavedPaymentMethod.objects.filter(
                user=user
            )

    def clean(self):
        cleaned = super().clean()
        saved = cleaned.get("saved_method")
        if saved:
            if saved.user_id != self.user.pk:
                raise forms.ValidationError("Invalid saved payment method.")
            return cleaned

        method = cleaned.get("payment_method")
        if not method:
            raise forms.ValidationError("Choose JazzCash or bank debit card.")
        if method == "jazzcash":
            phone = (cleaned.get("jazzcash_phone") or "").strip()
            if len(phone) < 10:
                raise forms.ValidationError(
                    {"jazzcash_phone": "Enter a valid JazzCash mobile number."}
                )
            cleaned["jazzcash_phone"] = phone
        elif method == "debit_card":
            number = "".join(c for c in (cleaned.get("card_number") or "") if c.isdigit())
            if len(number) < 12 or len(number) > 19:
                raise forms.ValidationError(
                    {"card_number": "Enter a valid debit card number."}
                )
            if not (cleaned.get("cardholder_name") or "").strip():
                raise forms.ValidationError(
                    {"cardholder_name": "Enter the name on card."}
                )
            if cleaned.get("card_exp_month") is None or cleaned.get("card_exp_year") is None:
                raise forms.ValidationError("Enter card expiry month and year.")
            cvv = (cleaned.get("card_cvv") or "").strip()
            if len(cvv) < 3:
                raise forms.ValidationError({"card_cvv": "Enter CVV."})
            cleaned["card_number_digits"] = number

        return cleaned
