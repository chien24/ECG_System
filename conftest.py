"""
Root conftest.py — shared fixtures dùng chung cho toàn bộ test suite.
"""
import numpy as np
import pytest


@pytest.fixture
def api_client():
    """Django test client tiện lợi."""
    from django.test import Client
    return Client()


@pytest.fixture
def user(db):
    """Tạo user thường để dùng trong test."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="StrongPass123!",
    )


@pytest.fixture
def admin_user(db):
    """Tạo admin user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_superuser(
        username="adminuser",
        email="admin@example.com",
        password="AdminPass123!",
    )


@pytest.fixture
def auth_client(user):
    """Client đã đăng nhập với user thường."""
    from django.test import Client
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(admin_user):
    """Client đã đăng nhập với admin."""
    from django.test import Client
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.fixture
def sample_ecg_signal():
    """Tín hiệu ECG mẫu (625 samples @ 125Hz = 5 giây)."""
    fs = 125
    t = np.linspace(0, 5, fs * 5)
    signal = (
        1.0 * np.sin(2 * np.pi * 1.2 * t)
        + 0.3 * np.sin(2 * np.pi * 2.4 * t)
        + 0.05 * np.random.randn(len(t))
    )
    return signal.astype(np.float64)
