from django import forms

from .models import Accounts, SavedPaymentMethod

class RegistrationForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Enter First Name', 'class': 'form-control'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Enter Last Name', 'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Enter Email', 'class': 'form-control'}))
    phone_no = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Enter Phone Number', 'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter Password', 'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password', 'class': 'form-control'}))
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'email', 'phone_no', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data
                
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])

        if commit:
            user.save()

        return user

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Enter Email', 'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter Password', 'class': 'form-control'}))


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = Accounts
        fields = ["username", "first_name", "last_name", "email", "phone_no"]
        widgets = {
            "username": forms.TextInput(
                attrs={"placeholder": "Username", "class": "form-control"}
            ),
            "first_name": forms.TextInput(
                attrs={"placeholder": "First name", "class": "form-control"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Last name", "class": "form-control"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "Email", "class": "form-control"}
            ),
            "phone_no": forms.TextInput(
                attrs={"placeholder": "Phone number", "class": "form-control"}
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        qs = Accounts.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = Accounts.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username


class SavedPaymentMethodForm(forms.ModelForm):
    card_number = forms.CharField(
        required=False,
        max_length=23,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Card number (not stored in full)"}
        ),
    )

    class Meta:
        model = SavedPaymentMethod
        fields = [
            "method_type",
            "label",
            "jazzcash_phone",
            "cardholder_name",
            "card_exp_month",
            "card_exp_year",
            "is_default",
        ]
        widgets = {
            "method_type": forms.Select(attrs={"class": "form-control"}),
            "label": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional label"}),
            "jazzcash_phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "03XX XXXXXXX"}
            ),
            "cardholder_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Name on card"}
            ),
            "card_exp_month": forms.NumberInput(attrs={"class": "form-control", "placeholder": "MM"}),
            "card_exp_year": forms.NumberInput(attrs={"class": "form-control", "placeholder": "YYYY"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        mt = cleaned.get("method_type")
        if mt == SavedPaymentMethod.METHOD_JAZZCASH:
            if not (cleaned.get("jazzcash_phone") or "").strip():
                raise forms.ValidationError("Enter your JazzCash mobile number.")
        elif mt == SavedPaymentMethod.METHOD_DEBIT_CARD:
            digits = "".join(c for c in (cleaned.get("card_number") or "") if c.isdigit())
            if len(digits) < 12:
                raise forms.ValidationError(
                    {"card_number": "Enter a valid card number (only last 4 digits are saved)."}
                )
            if not (cleaned.get("cardholder_name") or "").strip():
                raise forms.ValidationError({"cardholder_name": "Enter the name on card."})
            if cleaned.get("card_exp_month") is None or cleaned.get("card_exp_year") is None:
                raise forms.ValidationError("Enter expiry month and year.")
            cleaned["_card_digits"] = digits
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.user = self._user
        if obj.method_type == SavedPaymentMethod.METHOD_DEBIT_CARD:
            digits = self.cleaned_data.get("_card_digits", "")
            obj.card_last_four = digits[-4:]
        if commit:
            if obj.is_default:
                SavedPaymentMethod.objects.filter(user=obj.user).update(is_default=False)
            elif not SavedPaymentMethod.objects.filter(user=obj.user).exists():
                obj.is_default = True
            obj.save()
        return obj