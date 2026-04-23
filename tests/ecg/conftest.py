"""
tests/ecg/conftest.py — fixtures riêng cho app ecg.
"""
import uuid

import pytest


@pytest.fixture
def model_version(db):
    """Tạo ModelVersion active để dùng trong test."""
    from ecg.models import ModelVersion
    return ModelVersion.objects.create(
        model_name="ECG_CNN",
        version="1.0",
        model_path="model/best_epoch_5_loss_0.1693.pth",
        is_active=True,
    )


@pytest.fixture
def ecg_signal(db, user):
    """Tạo ECGSignal gắn với user."""
    from ecg.models import ECGSignal
    return ECGSignal.objects.create(
        user=user,
        signal_file="test_ecg.csv",
        sampling_rate=125,
        duration=5.0,
    )


@pytest.fixture
def guest_ecg_signal(db):
    """Tạo ECGSignal không gắn user (khách vãng lai)."""
    from ecg.models import ECGSignal
    return ECGSignal.objects.create(
        user=None,
        signal_file="guest_ecg.csv",
        sampling_rate=125,
        duration=3.0,
    )


@pytest.fixture
def prediction(db, ecg_signal, model_version):
    """Tạo Prediction liên kết ECGSignal + ModelVersion."""
    from ecg.models import Prediction
    return Prediction.objects.create(
        signal=ecg_signal,
        model=model_version,
        predicted_class=0,
        confidence_score=0.92,
        mapped_result="Bình thường",
    )
