import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ECGSignal(models.Model):
    """
    Tương ứng bảng ECG_SIGNAL trong biểu đồ CSDL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecg_signals",
    )
    signal_file = models.CharField(max_length=255)
    sampling_rate = models.IntegerField()
    duration = models.FloatField()
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.signal_file} ({self.id})"


class ModelVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    model_path = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.model_name} v{self.version}"


class Prediction(models.Model):
    """
    Tương ứng bảng PREDICTION trong biểu đồ CSDL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signal = models.ForeignKey(
        ECGSignal, on_delete=models.CASCADE, related_name="predictions"
    )
    model = models.ForeignKey(
        ModelVersion, on_delete=models.PROTECT, related_name="predictions"
    )
    predicted_class = models.IntegerField()
    confidence_score = models.FloatField()
    mapped_result = models.CharField(max_length=20)
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.mapped_result} ({self.predicted_class})"

