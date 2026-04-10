from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("dang-nhap/", views.CustomLoginView.as_view(), name="login"),
    path("dang-ky/", views.RegisterView.as_view(), name="register"),
    path("dang-xuat/", views.CustomLogoutView.as_view(), name="logout"),
    path("thong-ke/", views.system_stats, name="stats"),
]
