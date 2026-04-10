from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from ecg.models import ECGSignal, Prediction
from .forms import UserRegistrationForm

User = get_user_model()


class CustomLoginView(LoginView):
    template_name = "users/login.html"
    redirect_authenticated_user = True


class CustomLogoutView(View):
    """Đăng xuất và hiển thị trang xác nhận."""

    def get(self, request):
        logout(request)
        return render(request, "users/logged_out.html")

    def post(self, request):
        logout(request)
        return render(request, "users/logged_out.html")


class RegisterView(View):
    """Đăng ký tài khoản người dùng mới."""

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("ecg:home")
        form = UserRegistrationForm()
        return render(request, "users/register.html", {"form": form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("ecg:home")
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            login(request, user)
            return redirect("ecg:home")
        return render(request, "users/register.html", {"form": form})


@staff_member_required
def system_stats(request):
    """Trang thống kê hệ thống (dành cho Admin)."""
    total_signals = ECGSignal.objects.count()
    total_predictions = Prediction.objects.count()
    normal_count = Prediction.objects.filter(mapped_result="Bình thường").count()
    abnormal_count = Prediction.objects.filter(mapped_result="Bất thường").count()

    recent = timezone.now() - timedelta(days=7)
    predictions_7d = Prediction.objects.filter(timestamp__gte=recent)
    by_day = (
        predictions_7d.annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    context = {
        "total_signals": total_signals,
        "total_predictions": total_predictions,
        "normal_count": normal_count,
        "abnormal_count": abnormal_count,
        "predictions_7d_count": predictions_7d.count(),
        "by_day": list(by_day),
    }
    return render(request, "users/stats.html", context)
