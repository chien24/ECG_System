"""
tests/users/test_views.py — kiểm thử views của app users.

Bao gồm:
  - Login (GET/POST, redirect khi đã đăng nhập)
  - Logout (GET/POST)
  - Register (GET/POST valid/invalid)
  - system_stats (staff_member_required)
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestLoginView:
    def test_get_login_page_200(self, client):
        url = reverse("users:login")
        response = client.get(url)
        assert response.status_code == 200

    def test_login_valid_credentials(self, client, user):
        url = reverse("users:login")
        response = client.post(url, {
            "username": "testuser",
            "password": "StrongPass123!",
        })
        # Redirect sau login thành công
        assert response.status_code == 302

    def test_login_invalid_credentials(self, client, user):
        url = reverse("users:login")
        response = client.post(url, {
            "username": "testuser",
            "password": "WrongPassword!",
        })
        assert response.status_code == 200
        # Form lỗi → không redirect

    def test_login_already_authenticated_redirects(self, auth_client):
        url = reverse("users:login")
        response = auth_client.get(url)
        # redirect_authenticated_user=True → redirect đi
        assert response.status_code == 302

    def test_login_empty_fields(self, client):
        url = reverse("users:login")
        response = client.post(url, {"username": "", "password": ""})
        assert response.status_code == 200


@pytest.mark.django_db
class TestLogoutView:
    def test_logout_get(self, auth_client):
        url = reverse("users:logout")
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_logout_post(self, auth_client):
        url = reverse("users:logout")
        response = auth_client.post(url)
        assert response.status_code == 200

    def test_logout_unauthenticated_get(self, client):
        """Khách vãng lai truy cập logout → vẫn 200 (không crash)."""
        url = reverse("users:logout")
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestRegisterView:
    def test_get_register_page_200(self, client):
        url = reverse("users:register")
        response = client.get(url)
        assert response.status_code == 200

    def test_register_authenticated_redirects(self, auth_client):
        url = reverse("users:register")
        response = auth_client.get(url)
        assert response.status_code == 302

    def test_register_valid_data_creates_user(self, client, registration_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        url = reverse("users:register")
        response = client.post(url, registration_data)
        assert response.status_code == 302
        assert User.objects.filter(username="newuser").exists()

    def test_register_duplicate_username(self, client, user, registration_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Dùng username đã tồn tại
        registration_data["username"] = "testuser"
        registration_data["email"] = "unique2@x.com"

        url = reverse("users:register")
        response = client.post(url, registration_data)
        assert response.status_code == 200
        # Không tạo thêm user
        assert User.objects.filter(username="testuser").count() == 1

    def test_register_password_mismatch(self, client):
        url = reverse("users:register")
        response = client.post(url, {
            "username": "mismatchuser",
            "email": "mm@x.com",
            "password": "Pass123!",
            "password_confirm": "DifferentPass!",
        })
        assert response.status_code == 200

    def test_register_missing_fields(self, client):
        url = reverse("users:register")
        response = client.post(url, {"username": "nopass"})
        assert response.status_code == 200


@pytest.mark.django_db
class TestSystemStatsView:
    def test_redirect_non_staff(self, auth_client):
        url = reverse("users:stats")
        response = auth_client.get(url)
        # staff_member_required → redirect
        assert response.status_code == 302

    def test_admin_can_access(self, admin_client):
        url = reverse("users:stats")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_stats_context_keys(self, admin_client):
        url = reverse("users:stats")
        response = admin_client.get(url)
        ctx = response.context
        assert "total_signals" in ctx
        assert "total_predictions" in ctx
        assert "normal_count" in ctx
        assert "abnormal_count" in ctx
        assert "predictions_7d_count" in ctx
        assert "by_day" in ctx

    def test_unauthenticated_redirected(self, client):
        url = reverse("users:stats")
        response = client.get(url)
        assert response.status_code == 302
