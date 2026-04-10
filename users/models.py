import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Bảng Users theo ERD 2_7.png.
    - id: UUID (PK)
    - username: VARCHAR(150)
    - email: VARCHAR(150)
    - password_hash: Django dùng trường 'password' lưu bản hash
    - date_joined: DATETIME
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField("Tên đăng nhập", max_length=150, unique=True)
    email = models.EmailField("email", max_length=150, unique=True)
    date_joined = models.DateTimeField("ngày tham gia", default=timezone.now)

    class Meta:
        verbose_name = "người dùng"
        verbose_name_plural = "người dùng"

    def __str__(self):
        return self.username
