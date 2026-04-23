"""
tests/users/test_models.py — kiểm thử User model (AbstractUser custom).
"""
import uuid

import pytest


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPass123!",
        )

        assert user.pk is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.check_password("StrongPass123!")

    def test_user_str(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.create_user(
            username="alice", email="alice@x.com", password="Pass123!"
        )
        assert str(user) == "alice"

    def test_user_uuid_pk(self, user):
        assert isinstance(user.id, uuid.UUID)

    def test_unique_username(self, user):
        from django.contrib.auth import get_user_model
        from django.db import IntegrityError
        User = get_user_model()

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username="testuser",  # trùng với fixture user
                email="another@x.com",
                password="Pass123!",
            )

    def test_unique_email(self, user):
        from django.contrib.auth import get_user_model
        from django.db import IntegrityError
        User = get_user_model()

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username="anotheruser",
                email="testuser@example.com",  # trùng email fixture user
                password="Pass123!",
            )

    def test_create_superuser(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        admin = User.objects.create_superuser(
            username="superadmin",
            email="admin@x.com",
            password="AdminPass123!",
        )
        assert admin.is_staff is True
        assert admin.is_superuser is True

    def test_date_joined_auto_set(self, user):
        assert user.date_joined is not None

    def test_password_is_hashed(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.create_user(
            username="hashtest", email="hash@x.com", password="RawPass123!"
        )
        # Password không được lưu raw
        assert user.password != "RawPass123!"
        assert user.check_password("RawPass123!")
