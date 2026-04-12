import base64
from io import BytesIO
from pathlib import Path

from django.http import FileResponse, Http404, HttpResponse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from model.model import model, predict, device
from .models import ECGSignal, ModelVersion, Prediction


CLASS_LABELS = {
    0: "Nhịp bình thường (Normal)",
    1: "Nhịp trên thất bất thường (Supraventricular)",
    2: "Nhịp thất bất thường (Ventricular)",
    3: "Nhịp hợp nhất (Fusion)",
    4: "Không xác định (Unknown)",
}


def _interpret_predictions(preds_tensor):
    """
    Quy ước hiển thị:
    - Lớp 0  -> "Bình thường"
    - Lớp 1-4 -> "Bất thường"
    """
    preds = preds_tensor.detach().cpu().numpy()
    unique, counts = np.unique(preds, return_counts=True)

    distribution = []
    for cls, count in zip(unique, counts):
        cls_int = int(cls)
        distribution.append(
            {
                "class_index": cls_int,
                "label": CLASS_LABELS.get(cls_int, f"Lớp {cls_int}"),
                "count": int(count),
                "status": "Bình thường" if cls_int == 0 else "Bất thường",
            }
        )

    overall_status = "Bình thường" if np.all(preds == 0) else "Bất thường"
    return overall_status, distribution


def _plot_ecg_to_base64(raw_signal, sampling_rate=125):
    """
    Vẽ biểu đồ tín hiệu ECG và trả về chuỗi base64 PNG (không lưu file).
    """
    fig, ax = plt.subplots(figsize=(12, 4), facecolor="#1e293b")
    ax.set_facecolor("#1e293b")

    n_samples = len(raw_signal)
    time_axis = np.arange(n_samples) / sampling_rate

    ax.plot(time_axis, raw_signal, color="#22c55e", linewidth=0.8)
    ax.set_xlabel("Thời gian (giây)", color="#94a3b8", fontsize=10)
    ax.set_ylabel("Biên độ", color="#94a3b8", fontsize=10)
    ax.set_title("Tín hiệu ECG", color="#e5e7eb", fontsize=12)
    ax.tick_params(colors="#94a3b8")
    ax.spines["bottom"].set_color("#475569")
    ax.spines["left"].set_color("#475569")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(
        buf,
        format="png",
        dpi=100,
        facecolor="#1e293b",
        edgecolor="none",
        bbox_inches="tight",
    )
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def home(request):
    """
    Trang tổng quan chính của hệ thống.
    """
    return render(request, "ecg/home.html")


def realtime_dashboard(request):
    """
    Trang dashboard phân tích ECG thời gian thực qua WebSocket.
    """
    return render(request, "ecg/realtime_dashboard.html")


def analyze_upload(request):
    """
    Giao diện chính cho phép người dùng tải file ECG (CSV)
    và xem kết quả phân loại: Bình thường / Bất thường.
    Đồng thời, tự động dọn dẹp lịch sử khách vãng lai cũ hơn 1 ngày.
    """
    # Tự động xóa lịch sử khách vãng lai (user=None) cũ hơn 1 ngày
    cutoff = timezone.now() - timezone.timedelta(days=1)
    old_guest_signals = ECGSignal.objects.filter(user__isnull=True, uploaded_at__lt=cutoff)
    old_guest_signals.delete()  # CASCADE tự xóa Prediction liên quan

    context = {}

    if request.method == "POST" and request.FILES.get("ecg_file"):
        uploaded_file = request.FILES["ecg_file"]

        # Lưu tạm file để xử lý
        upload_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "uploads"))
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / uploaded_file.name

        with default_storage.open(str(file_path), "wb+") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        try:
            # Giả định file CSV 1 cột là tín hiệu ECG
            df = pd.read_csv(file_path, header=None)
            raw_signal = df.iloc[:, 0].values.astype(float)
        except Exception:
            context["error"] = "Không đọc được file ECG. Vui lòng kiểm tra lại định dạng (CSV, 1 cột)."
            return render(request, "ecg/analyze_upload.html", context)

        if model is None:
            context["error"] = "Không tải được mô hình nhận dạng ECG."
            return render(request, "ecg/analyze_upload.html", context)

        preds_tensor = predict(raw_signal, model, device)
        overall_status, distribution = _interpret_predictions(preds_tensor)

        # Lưu thông tin theo các bảng trong biểu đồ CSDL
        sampling_rate = 125
        duration_seconds = float(len(raw_signal) / sampling_rate)

        ecg_signal = ECGSignal.objects.create(
            user=request.user if request.user.is_authenticated else None,
            signal_file=str(file_path.name),
            sampling_rate=sampling_rate,
            duration=duration_seconds,
            uploaded_at=timezone.now(),
        )

        model_version, _ = ModelVersion.objects.get_or_create(
            is_active=True,
            model_name="ECG_CNN",
            version="1.0",
            defaults={
                "model_path": r".\model\best_epoch_4_acc_0.1791.pth",
                "created_at": timezone.now(),
            },
        )

        # Chọn lớp chiếm đa số để lưu vào bảng Prediction (5 lớp gốc)
        # nhưng mapped_result phải tuân theo quy tắc hiển thị:
        # - Bình thường: tất cả nhịp đều thuộc lớp 0
        # - Bất thường: chỉ cần tồn tại nhịp thuộc lớp 1–4
        np_preds = preds_tensor.detach().cpu().numpy()
        unique, counts = np.unique(np_preds, return_counts=True)
        majority_index = int(unique[np.argmax(counts)])
        confidence = float(np.max(counts) / np.sum(counts)) if np.sum(counts) else 0.0
        mapped_result = overall_status

        Prediction.objects.create(
            signal=ecg_signal,
            model=model_version,
            predicted_class=majority_index,
            confidence_score=confidence,
            mapped_result=mapped_result,
            timestamp=timezone.now(),
            created_at=timezone.now(),
        )

        ecg_chart_base64 = _plot_ecg_to_base64(raw_signal, sampling_rate)

        context.update(
            {
                "overall_status": overall_status,
                "distribution": distribution,
                "file_name": uploaded_file.name,
                "ecg_chart_base64": ecg_chart_base64,
            }
        )

    return render(request, "ecg/analyze_upload.html", context)


@login_required(login_url="users:login")
def analysis_history(request):
    """
    Danh sách các lần dự đoán:
    - Admin (is_staff) thấy TẤT CẢ lịch sử.
    - User thường chỉ thấy lịch sử của chính mình.
    - Khách vãng lai bị chuyển hướng đến trang đăng nhập.
    """
    if request.user.is_staff:
        predictions = (
            Prediction.objects.select_related("signal", "model", "signal__user")
            .order_by("-timestamp")[:100]
        )
        is_admin_view = True
    else:
        predictions = (
            Prediction.objects.select_related("signal", "model")
            .filter(signal__user=request.user)
            .order_by("-timestamp")[:50]
        )
        is_admin_view = False

    return render(
        request,
        "ecg/history.html",
        {
            "predictions": predictions,
            "is_admin_view": is_admin_view,
        },
    )


@login_required(login_url="users:login")
def prediction_detail(request, prediction_id):
    """
    Chi tiết một lần dự đoán:
    - Admin xem được tất cả.
    - User thường chỉ xem được của chính mình.
    """
    if request.user.is_staff:
        prediction = get_object_or_404(
            Prediction.objects.select_related("signal", "model"),
            id=prediction_id,
        )
    else:
        prediction = get_object_or_404(
            Prediction.objects.select_related("signal", "model"),
            id=prediction_id,
            signal__user=request.user,
        )
    return render(
        request,
        "ecg/prediction_detail.html",
        {
            "prediction": prediction,
        },
    )


@login_required(login_url="users:login")
@require_POST
def delete_analysis_history(request):
    """
    Xóa lịch sử phân tích ECG:
    - Admin: xóa bất kỳ bản ghi nào (action='selected' hoặc action='all').
    - User thường: chỉ xóa lịch sử của chính mình.
    """
    action = request.POST.get("action")

    if request.user.is_staff:
        # Admin xóa toàn bộ hoặc theo lựa chọn
        if action == "all":
            Prediction.objects.all().delete()
        else:
            ids = request.POST.getlist("selected_predictions")
            if ids:
                Prediction.objects.filter(id__in=ids).delete()
    else:
        # User thường chỉ được xóa lịch sử của mình
        if action == "all":
            Prediction.objects.filter(signal__user=request.user).delete()
        else:
            ids = request.POST.getlist("selected_predictions")
            if ids:
                Prediction.objects.filter(
                    id__in=ids,
                    signal__user=request.user,
                ).delete()

    return redirect("ecg:analysis_history")


@login_required(login_url="users:login")
def download_ecg_csv(request, prediction_id):
    """
    Tải xuống file CSV tín hiệu ECG gốc.
    - Admin tải được của bất kỳ ai.
    - User thường chỉ tải được của chính mình.
    """
    if request.user.is_staff:
        prediction = get_object_or_404(
            Prediction.objects.select_related("signal"),
            id=prediction_id,
        )
    else:
        prediction = get_object_or_404(
            Prediction.objects.select_related("signal"),
            id=prediction_id,
            signal__user=request.user,
        )

    upload_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "uploads"))
    file_path = upload_dir / prediction.signal.signal_file

    if not file_path.exists():
        raise Http404("File CSV không tồn tại trên máy chủ.")

    response = FileResponse(
        open(file_path, "rb"),
        content_type="text/csv",
        as_attachment=True,
        filename=prediction.signal.signal_file,
    )
    return response


@login_required(login_url="users:login")
def download_ecg_chart(request, prediction_id):
    """
    Tạo và tải xuống biểu đồ tín hiệu ECG dưới dạng ảnh PNG.
    - Admin tải được của bất kỳ ai.
    - User thường chỉ tải được của chính mình.
    """
    if request.user.is_staff:
        prediction = get_object_or_404(
            Prediction.objects.select_related("signal"),
            id=prediction_id,
        )
    else:
        prediction = get_object_or_404(
            Prediction.objects.select_related("signal"),
            id=prediction_id,
            signal__user=request.user,
        )

    upload_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "uploads"))
    file_path = upload_dir / prediction.signal.signal_file

    if not file_path.exists():
        raise Http404("File CSV không tồn tại trên máy chủ, không thể tạo biểu đồ.")

    try:
        df = pd.read_csv(file_path, header=None)
        raw_signal = df.iloc[:, 0].values.astype(float)
    except Exception:
        raise Http404("Không đọc được file CSV để tạo biểu đồ.")

    sampling_rate = prediction.signal.sampling_rate or 125
    chart_b64 = _plot_ecg_to_base64(raw_signal, sampling_rate)
    png_bytes = base64.b64decode(chart_b64)

    chart_filename = Path(prediction.signal.signal_file).stem + "_ecg_chart.png"
    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{chart_filename}"'
    return response
