"""
tests/users/conftest.py — fixtures riêng cho app users.
"""
import pytest


@pytest.fixture
def registration_data():
    return {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
    }
