"""
tests/ecg/test_models.py — kiểm thử ECG models.

Bao gồm:
  - ECGSignal: tạo, ForeignKey, cascade delete
  - ModelVersion: tạo, trường is_active
  - Prediction: tạo, ForeignKey tới ECGSignal + ModelVersion
"""
import uuid

import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestECGSignalModel:
    """Test model ECGSignal."""

    def test_create_ecg_signal_with_user(self, user):
        from ecg.models import ECGSignal

        signal = ECGSignal.objects.create(
            user=user,
            signal_file="test.csv",
            sampling_rate=125,
            duration=10.0,
        )

        assert signal.pk is not None
        assert isinstance(signal.id, uuid.UUID)
        assert signal.user == user
        assert signal.signal_file == "test.csv"
        assert signal.sampling_rate == 125
        assert signal.duration == 10.0
        assert signal.uploaded_at is not None

    def test_create_ecg_signal_without_user(self):
        """Khách vãng lai: user=None."""
        from ecg.models import ECGSignal

        signal = ECGSignal.objects.create(
            user=None,
            signal_file="guest.csv",
            sampling_rate=125,
            duration=5.0,
        )

        assert signal.user is None
        assert ECGSignal.objects.filter(user__isnull=True).count() == 1

    def test_ecg_signal_str(self, ecg_signal):
        """__str__ phải có dạng 'filename (uuid)'."""
        assert "test_ecg.csv" in str(ecg_signal)
        assert str(ecg_signal.id) in str(ecg_signal)

    def test_ecg_signal_related_name(self, user, ecg_signal):
        """user.ecg_signals truy cập ngược được."""
        assert ecg_signal in user.ecg_signals.all()

    def test_delete_user_sets_signal_null(self, db, user):
        """on_delete=SET_NULL: xóa user → signal.user = None."""
        from ecg.models import ECGSignal

        signal = ECGSignal.objects.create(
            user=user,
            signal_file="del_test.csv",
            sampling_rate=125,
            duration=5.0,
        )
        user_id = user.pk
        user.delete()

        signal.refresh_from_db()
        assert signal.user is None

    def test_ecg_signal_uuid_is_auto_generated(self):
        """Mỗi signal phải có UUID khác nhau."""
        from ecg.models import ECGSignal

        s1 = ECGSignal.objects.create(signal_file="a.csv", sampling_rate=125, duration=1.0)
        s2 = ECGSignal.objects.create(signal_file="b.csv", sampling_rate=125, duration=1.0)
        assert s1.id != s2.id


@pytest.mark.django_db
class TestModelVersionModel:
    """Test model ModelVersion."""

    def test_create_model_version(self):
        from ecg.models import ModelVersion

        mv = ModelVersion.objects.create(
            model_name="ECG_CNN",
            version="2.0",
            model_path="model/v2.pth",
            is_active=True,
        )

        assert mv.pk is not None
        assert mv.model_name == "ECG_CNN"
        assert mv.version == "2.0"
        assert mv.is_active is True

    def test_model_version_str(self, model_version):
        assert "ECG_CNN" in str(model_version)
        assert "1.0" in str(model_version)

    def test_default_is_active_true(self):
        from ecg.models import ModelVersion

        mv = ModelVersion.objects.create(
            model_name="TestModel",
            version="0.1",
            model_path="model/test.pth",
        )
        assert mv.is_active is True

    def test_model_version_uuid_pk(self, model_version):
        assert isinstance(model_version.id, uuid.UUID)


@pytest.mark.django_db
class TestPredictionModel:
    """Test model Prediction."""

    def test_create_prediction(self, ecg_signal, model_version):
        from ecg.models import Prediction

        pred = Prediction.objects.create(
            signal=ecg_signal,
            model=model_version,
            predicted_class=0,
            confidence_score=0.95,
            mapped_result="Bình thường",
        )

        assert pred.pk is not None
        assert pred.signal == ecg_signal
        assert pred.model == model_version
        assert pred.predicted_class == 0
        assert pred.confidence_score == pytest.approx(0.95)
        assert pred.mapped_result == "Bình thường"

    def test_prediction_str(self, prediction):
        s = str(prediction)
        assert "Bình thường" in s
        assert "0" in s

    def test_prediction_cascade_delete(self, db, ecg_signal, model_version):
        """Xóa ECGSignal → Prediction bị xóa theo (CASCADE)."""
        from ecg.models import Prediction

        pred = Prediction.objects.create(
            signal=ecg_signal,
            model=model_version,
            predicted_class=1,
            confidence_score=0.80,
            mapped_result="Bất thường",
        )
        pred_id = pred.id
        ecg_signal.delete()

        assert not Prediction.objects.filter(id=pred_id).exists()

    def test_prediction_protect_model_version(self, prediction, model_version):
        """on_delete=PROTECT: không xóa được ModelVersion khi còn Prediction."""
        from django.db.models import ProtectedError

        with pytest.raises(ProtectedError):
            model_version.delete()

    def test_prediction_related_name(self, ecg_signal, prediction):
        """ecg_signal.predictions truy cập ngược."""
        assert prediction in ecg_signal.predictions.all()

    def test_abnormal_prediction(self, ecg_signal, model_version):
        from ecg.models import Prediction

        pred = Prediction.objects.create(
            signal=ecg_signal,
            model=model_version,
            predicted_class=2,
            confidence_score=0.73,
            mapped_result="Bất thường",
        )
        assert pred.mapped_result == "Bất thường"
        assert pred.predicted_class == 2

    def test_prediction_confidence_range(self, ecg_signal, model_version):
        """confidence_score nằm trong [0, 1]."""
        from ecg.models import Prediction

        pred = Prediction.objects.create(
            signal=ecg_signal,
            model=model_version,
            predicted_class=0,
            confidence_score=0.0,
            mapped_result="Bình thường",
        )
        assert 0.0 <= pred.confidence_score <= 1.0
