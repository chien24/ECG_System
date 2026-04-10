from django.contrib import admin

from .models import ECGSignal, ModelVersion, Prediction


@admin.register(ECGSignal)
class ECGSignalAdmin(admin.ModelAdmin):
    list_display = ("signal_file", "user", "sampling_rate", "duration", "uploaded_at")
    search_fields = ("signal_file", "user__username", "user__email")
    list_filter = ("uploaded_at",)


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ("model_name", "version", "is_active", "created_at")
    list_filter = ("is_active", "created_at")


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = (
        "signal",
        "model",
        "predicted_class",
        "mapped_result",
        "confidence_score",
        "timestamp",
    )
    list_filter = ("mapped_result", "timestamp", "model")
    search_fields = ("signal__signal_file",)

