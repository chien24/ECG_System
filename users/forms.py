import re

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

# Regex: chỉ chữ cái, số, dấu gạch dưới
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")


def validate_password_strength(password: str) -> None:
    """Kiểm tra mật khẩu: tối thiểu 8 ký tự, có chữ hoa, chữ thường, số."""
    if len(password) < 8:
        raise ValidationError("Mật khẩu phải có ít nhất 8 ký tự.")
    if not any(c.isupper() for c in password):
        raise ValidationError("Mật khẩu phải có ít nhất một chữ in hoa.")
    if not any(c.islower() for c in password):
        raise ValidationError("Mật khẩu phải có ít nhất một chữ thường.")
    if not any(c.isdigit() for c in password):
        raise ValidationError("Mật khẩu phải có ít nhất một chữ số.")


class UserRegistrationForm(forms.Form):
    """
    Form đăng ký người dùng mới.
    - username: 4-30 ký tự, chữ/số/gạch dưới, unique, trim
    - email: bắt buộc, format email, unique, lowercase, trim
    - password: min 8, chữ hoa + chữ thường + số, hash bằng Django (PBKDF2/Argon2)
    """

    username = forms.CharField(
        label="Tên đăng nhập",
        min_length=4,
        max_length=30,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control user-input",
                "placeholder": "4–30 ký tự, chữ/số/gạch dưới",
                "autocomplete": "username",
            }
        ),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control user-input",
                "placeholder": "example@email.com",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        label="Mật khẩu",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control user-input",
                "placeholder": "Tối thiểu 8 ký tự, có chữ hoa, thường, số",
                "autocomplete": "new-password",
            }
        ),
    )
    password_confirm = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control user-input",
                "placeholder": "Nhập lại mật khẩu",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if len(username) < 4:
            raise ValidationError("Tên đăng nhập phải có từ 4 đến 30 ký tự.")
        if len(username) > 30:
            raise ValidationError("Tên đăng nhập không được quá 30 ký tự.")
        if not USERNAME_REGEX.match(username):
            raise ValidationError(
                "Tên đăng nhập chỉ được chứa chữ cái, số và dấu gạch dưới."
            )
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Tên đăng nhập này đã được sử dụng.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email không được để trống.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email này đã được đăng ký.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        validate_password_strength(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", ValidationError("Hai mật khẩu không trùng khớp."))
        return cleaned_data
