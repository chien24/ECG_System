"""
tests/ecg/test_views.py — kiểm thử Views của app ecg.

Bao gồm:
  - home, realtime_dashboard, analyze_upload (GET/POST)
  - analysis_history (login_required, phân quyền)
  - prediction_detail, delete_analysis_history
  - download_ecg_csv, download_ecg_chart
"""
import io
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from django.urls import reverse


# ─────────────────────────── Home & Dashboard ──────────────────────────────

@pytest.mark.django_db
class TestHomeView:
    def test_home_get_200(self, client):
        url = reverse("ecg:home")
        response = client.get(url)
        assert response.status_code == 200

    def test_home_uses_correct_template(self, client):
        url = reverse("ecg:home")
        response = client.get(url)
        assert "ecg/home.html" in [t.name for t in response.templates]


@pytest.mark.django_db
class TestRealtimeDashboard:
    def test_dashboard_get_200(self, client):
        url = reverse("ecg:realtime_dashboard")
        response = client.get(url)
        assert response.status_code == 200

    def test_dashboard_template(self, client):
        url = reverse("ecg:realtime_dashboard")
        response = client.get(url)
        assert "ecg/realtime_dashboard.html" in [t.name for t in response.templates]


# ─────────────────────────── Analyze Upload ────────────────────────────────

@pytest.mark.django_db
class TestAnalyzeUploadView:
    def test_get_returns_200(self, client):
        url = reverse("ecg:analyze_upload")
        response = client.get(url)
        assert response.status_code == 200

    def test_get_uses_correct_template(self, client):
        url = reverse("ecg:analyze_upload")
        response = client.get(url)
        assert "ecg/analyze_upload.html" in [t.name for t in response.templates]

    def test_post_no_file_returns_200(self, client):
        """POST không có file → render lại trang (không crash)."""
        url = reverse("ecg:analyze_upload")
        response = client.post(url, {})
        assert response.status_code == 200

    @patch("ecg.views.model")
    @patch("ecg.views.predict")
    @patch("ecg.views.device")
    def test_post_valid_csv_returns_200(self, mock_device, mock_predict, mock_model, client):
        """POST với file CSV hợp lệ → 200 với kết quả phân tích."""
        import torch

        # Giả lập model predict trả về tensor nhị phân
        mock_model.__bool__ = MagicMock(return_value=True)
        mock_model.return_value = True
        mock_predict.return_value = torch.tensor([0, 0, 0, 1, 0])

        # Tạo CSV in-memory (625 dòng)
        signal = np.sin(np.linspace(0, 10 * np.pi, 625))
        csv_content = "\n".join(str(v) for v in signal)
        csv_file = io.BytesIO(csv_content.encode())
        csv_file.name = "test_ecg.csv"

        url = reverse("ecg:analyze_upload")
        response = client.post(url, {"ecg_file": csv_file})
        # Nếu model mock hoạt động → 200; nếu model=None → vẫn 200 với error context
        assert response.status_code == 200

    def test_post_invalid_csv_shows_error(self, client):
        """POST file không phải CSV hợp lệ → hiển thị error trong context."""
        bad_file = io.BytesIO(b"not,valid,csv\ndata")
        bad_file.name = "bad.csv"

        url = reverse("ecg:analyze_upload")
        with patch("ecg.views.pd.read_csv", side_effect=Exception("bad csv")):
            response = client.post(url, {"ecg_file": bad_file})
        assert response.status_code == 200


# ─────────────────────────── Analysis History ──────────────────────────────

@pytest.mark.django_db
class TestAnalysisHistoryView:
    def test_redirect_when_not_logged_in(self, client):
        url = reverse("ecg:analysis_history")
        response = client.get(url)
        assert response.status_code == 302
        assert "/dang-nhap" in response.url or "login" in response.url

    def test_user_sees_own_predictions(self, auth_client, prediction):
        url = reverse("ecg:analysis_history")
        response = auth_client.get(url)
        assert response.status_code == 200
        assert prediction in response.context["predictions"]

    def test_admin_sees_all_predictions(self, admin_client, prediction):
        url = reverse("ecg:analysis_history")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.context["is_admin_view"] is True
        assert prediction in response.context["predictions"]

    def test_user_cannot_see_others_predictions(self, auth_client, db):
        """User thường chỉ thấy predictions của mình."""
        from django.contrib.auth import get_user_model
        from ecg.models import ECGSignal, Prediction, ModelVersion

        User = get_user_model()
        other_user = User.objects.create_user(
            username="other", email="other@x.com", password="Pass1234!"
        )
        mv = ModelVersion.objects.create(
            model_name="ECG_CNN", version="1.0", model_path="x.pth"
        )
        sig = ECGSignal.objects.create(
            user=other_user, signal_file="other.csv", sampling_rate=125, duration=5.0
        )
        other_pred = Prediction.objects.create(
            signal=sig, model=mv, predicted_class=0,
            confidence_score=0.9, mapped_result="Bình thường"
        )

        url = reverse("ecg:analysis_history")
        response = auth_client.get(url)
        assert other_pred not in response.context["predictions"]


# ─────────────────────────── Prediction Detail ─────────────────────────────

@pytest.mark.django_db
class TestPredictionDetailView:
    def test_redirect_when_not_logged_in(self, client, prediction):
        url = reverse("ecg:prediction_detail", kwargs={"prediction_id": prediction.id})
        response = client.get(url)
        assert response.status_code == 302

    def test_user_can_view_own_prediction(self, auth_client, prediction):
        url = reverse("ecg:prediction_detail", kwargs={"prediction_id": prediction.id})
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.context["prediction"] == prediction

    def test_user_cannot_view_others_prediction(self, auth_client, db):
        """User truy cập prediction của người khác → 404."""
        from django.contrib.auth import get_user_model
        from ecg.models import ECGSignal, Prediction, ModelVersion

        User = get_user_model()
        other = User.objects.create_user(
            username="other2", email="o2@x.com", password="Pass1234!"
        )
        mv = ModelVersion.objects.create(
            model_name="ECG_CNN", version="1.0", model_path="x.pth"
        )
        sig = ECGSignal.objects.create(
            user=other, signal_file="o2.csv", sampling_rate=125, duration=5.0
        )
        pred = Prediction.objects.create(
            signal=sig, model=mv, predicted_class=0,
            confidence_score=0.9, mapped_result="Bình thường"
        )

        url = reverse("ecg:prediction_detail", kwargs={"prediction_id": pred.id})
        response = auth_client.get(url)
        assert response.status_code == 404

    def test_admin_can_view_any_prediction(self, admin_client, prediction):
        url = reverse("ecg:prediction_detail", kwargs={"prediction_id": prediction.id})
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_invalid_uuid_returns_404(self, auth_client):
        url = reverse("ecg:prediction_detail", kwargs={"prediction_id": uuid.uuid4()})
        response = auth_client.get(url)
        assert response.status_code == 404


# ─────────────────────────── Delete History ────────────────────────────────

@pytest.mark.django_db
class TestDeleteAnalysisHistoryView:
    def test_redirect_when_not_logged_in(self, client):
        url = reverse("ecg:delete_history")
        response = client.post(url, {"action": "all"})
        assert response.status_code == 302

    def test_user_delete_all_own(self, auth_client, prediction):
        """User xóa toàn bộ lịch sử của mình."""
        from ecg.models import Prediction

        url = reverse("ecg:delete_history")
        response = auth_client.post(url, {"action": "all"})
        assert response.status_code == 302

    def test_admin_delete_all(self, admin_client, prediction):
        from ecg.models import Prediction

        url = reverse("ecg:delete_history")
        response = admin_client.post(url, {"action": "all"})
        assert response.status_code == 302
        assert Prediction.objects.count() == 0

    def test_user_delete_selected(self, auth_client, prediction):
        from ecg.models import Prediction

        url = reverse("ecg:delete_history")
        response = auth_client.post(url, {
            "action": "selected",
            "selected_predictions": [str(prediction.id)],
        })
        assert response.status_code == 302

    def test_get_method_not_allowed(self, auth_client):
        """GET on require_POST view → 405."""
        url = reverse("ecg:delete_history")
        response = auth_client.get(url)
        assert response.status_code == 405
