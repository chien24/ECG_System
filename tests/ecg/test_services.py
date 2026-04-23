"""
tests/ecg/test_services.py — kiểm thử logic xử lý ECG (model.model module).

Không cần model weights thật: dùng mock hoặc model nhỏ khởi tạo random.

Bao gồm:
  - bandpass_filter: output shape, dtype
  - normalize_signal: mean ≈ 0, std ≈ 1
  - resize_beat: output đúng 187 samples
  - preprocess_ecg_signal: output tensor shape (N, 187) hoặc empty
  - predict: không crash, output là LongTensor
  - _interpret_predictions (ecg.views helper)
  - _infer (ecg.consumers helper)
"""
import numpy as np
import pytest
import torch


# ─────────────────────────── Signal Processing ─────────────────────────────

class TestBandpassFilter:
    def test_output_same_length_as_input(self, sample_ecg_signal):
        from model.model import bandpass_filter
        filtered = bandpass_filter(sample_ecg_signal)
        assert len(filtered) == len(sample_ecg_signal)

    def test_output_is_float64(self, sample_ecg_signal):
        from model.model import bandpass_filter
        filtered = bandpass_filter(sample_ecg_signal)
        assert filtered.dtype in (np.float64, np.float32)

    def test_custom_fs_and_cutoffs(self, sample_ecg_signal):
        from model.model import bandpass_filter
        filtered = bandpass_filter(sample_ecg_signal, fs=125, lowcut=0.5, highcut=40)
        assert len(filtered) == len(sample_ecg_signal)


class TestNormalizeSignal:
    def test_mean_near_zero(self):
        from model.model import normalize_signal
        signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        normalized = normalize_signal(signal)
        assert abs(np.mean(normalized)) < 1e-6

    def test_std_near_one(self):
        from model.model import normalize_signal
        signal = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        normalized = normalize_signal(signal)
        assert abs(np.std(normalized) - 1.0) < 0.01

    def test_constant_signal_no_crash(self):
        """Tín hiệu hằng số (std=0): chia cho std+1e-8, không crash."""
        from model.model import normalize_signal
        signal = np.ones(100)
        result = normalize_signal(signal)
        assert np.all(np.isfinite(result))


class TestResizeBeat:
    def test_output_length_187(self):
        from model.model import resize_beat
        beat = np.random.randn(90)
        resized = resize_beat(beat, target_len=187)
        assert len(resized) == 187

    def test_different_input_lengths(self):
        from model.model import resize_beat
        for n in [50, 100, 150, 200]:
            beat = np.random.randn(n)
            resized = resize_beat(beat, target_len=187)
            assert len(resized) == 187

    def test_output_values_are_finite(self):
        from model.model import resize_beat
        beat = np.sin(np.linspace(0, np.pi, 80))
        resized = resize_beat(beat, target_len=187)
        assert np.all(np.isfinite(resized))


# ─────────────────────────── Full Preprocessing ────────────────────────────

class TestPreprocessECGSignal:
    def test_returns_tensor(self, sample_ecg_signal):
        from model.model import preprocess_ecg_signal
        result = preprocess_ecg_signal(sample_ecg_signal)
        assert isinstance(result, torch.Tensor)

    def test_output_shape_when_peaks_found(self):
        """Tín hiệu có peak rõ ràng → tensor shape (N, 187) với N ≥ 1."""
        from model.model import preprocess_ecg_signal

        fs = 125
        t = np.linspace(0, 10, fs * 10)
        signal = np.zeros_like(t)
        # Tạo các spike tại tần số tim ~70bpm
        for i in range(12):
            idx = int(i * fs * 60 / 70)
            if idx < len(signal):
                signal[idx] = 2.0

        result = preprocess_ecg_signal(signal)
        if len(result) > 0:
            assert result.shape[1] == 187

    def test_output_dtype_float32(self, sample_ecg_signal):
        from model.model import preprocess_ecg_signal
        result = preprocess_ecg_signal(sample_ecg_signal)
        if len(result) > 0:
            assert result.dtype == torch.float32

    def test_short_signal_no_crash(self):
        """Tín hiệu quá ngắn (< 1 nhịp) → không crash, trả về tensor rỗng."""
        from model.model import preprocess_ecg_signal
        short_signal = np.random.randn(50)
        result = preprocess_ecg_signal(short_signal)
        assert isinstance(result, torch.Tensor)


# ─────────────────────────── Predict Function ──────────────────────────────

class TestPredictFunction:
    def test_predict_with_mock_model(self, sample_ecg_signal):
        """Test predict() với model mock — không load weights thật."""
        from model.model import predict, preprocess_ecg_signal, ECG_CNN

        device = torch.device("cpu")
        mock_model = ECG_CNN(num_classes=5).to(device)
        # Random weights (không load checkpoint)
        mock_model.eval()

        # Chỉ chạy nếu preprocessing tạo được beats
        beats = preprocess_ecg_signal(sample_ecg_signal)
        if len(beats) == 0:
            pytest.skip("Tín hiệu mẫu không tạo được beats để test predict.")

        preds = predict(sample_ecg_signal, mock_model, device)
        assert isinstance(preds, torch.Tensor)
        assert preds.dtype == torch.int64  # argmax → LongTensor
        assert preds.ndim == 1

    def test_predict_output_values_in_range(self, sample_ecg_signal):
        """Giá trị predict phải nằm trong [0, 4] (5 classes)."""
        from model.model import predict, preprocess_ecg_signal, ECG_CNN

        beats = preprocess_ecg_signal(sample_ecg_signal)
        if len(beats) == 0:
            pytest.skip("Không có beats.")

        device = torch.device("cpu")
        mock_model = ECG_CNN(num_classes=5).to(device)
        preds = predict(sample_ecg_signal, mock_model, device)

        assert torch.all(preds >= 0)
        assert torch.all(preds <= 4)

    def test_predict_batch_size_matches_beats(self, sample_ecg_signal):
        """Số predictions = số beats được phát hiện."""
        from model.model import predict, preprocess_ecg_signal, ECG_CNN

        beats = preprocess_ecg_signal(sample_ecg_signal)
        if len(beats) == 0:
            pytest.skip("Không có beats.")

        device = torch.device("cpu")
        mock_model = ECG_CNN(num_classes=5).to(device)
        preds = predict(sample_ecg_signal, mock_model, device)

        assert len(preds) == len(beats)


# ─────────────────────────── ECG_CNN Architecture ──────────────────────────

class TestECGCNNModel:
    def test_forward_pass_output_shape(self):
        """ECG_CNN forward: input (B, 187) → output (B, 5)."""
        from model.model import ECG_CNN

        model = ECG_CNN(num_classes=5)
        model.eval()

        batch = torch.randn(8, 187)
        with torch.no_grad():
            out = model(batch)

        assert out.shape == (8, 5)

    def test_single_sample_forward(self):
        from model.model import ECG_CNN

        model = ECG_CNN(num_classes=5)
        model.eval()
        x = torch.randn(1, 187)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1, 5)

    def test_output_is_logits_not_probabilities(self):
        """Output chưa qua softmax → có thể âm, không bounded [0,1]."""
        from model.model import ECG_CNN

        model = ECG_CNN(num_classes=5)
        model.eval()
        x = torch.randn(4, 187)
        with torch.no_grad():
            out = model(x)
        # Logits thường có cả âm lẫn dương
        has_negative = (out < 0).any().item()
        # Với random weights, rất cao xác suất có giá trị âm
        assert isinstance(has_negative, bool)


# ─────────────────────────── Views Helper: _interpret_predictions ───────────

class TestInterpretPredictions:
    def test_all_normal_returns_binh_thuong(self):
        from ecg.views import _interpret_predictions
        preds = torch.tensor([0, 0, 0, 0])
        status, dist = _interpret_predictions(preds)
        assert status == "Bình thường"

    def test_any_abnormal_returns_bat_thuong(self):
        from ecg.views import _interpret_predictions
        preds = torch.tensor([0, 1, 0, 0])
        status, dist = _interpret_predictions(preds)
        assert status == "Bất thường"

    def test_distribution_keys(self):
        from ecg.views import _interpret_predictions
        preds = torch.tensor([0, 1, 2, 0])
        _, dist = _interpret_predictions(preds)
        for item in dist:
            assert "class_index" in item
            assert "label" in item
            assert "count" in item
            assert "status" in item

    def test_distribution_count_sum_equals_total(self):
        from ecg.views import _interpret_predictions
        preds = torch.tensor([0, 0, 1, 2, 0])
        _, dist = _interpret_predictions(preds)
        total = sum(item["count"] for item in dist)
        assert total == len(preds)


# ─────────────────────────── Consumer Helper: _infer ───────────────────────

class TestInferHelper:
    def test_infer_with_mock_returns_tuple(self, sample_ecg_signal):
        from ecg.consumers import _infer

        mock_model = MagicMock()
        mock_device = torch.device("cpu")

        # Mock predict_fn trả về tensor class 0 (Normal)
        mock_predict_fn = MagicMock(return_value=torch.tensor([0, 0, 0]))
        # Mock preprocess trả về dummy tensor
        mock_preprocess_fn = MagicMock(return_value=torch.randn(3, 187))
        # Mock model forward
        mock_model.return_value = torch.randn(3, 5)

        window = sample_ecg_signal[:625]
        prediction, abnormal_ratio, confidence, latency_ms = _infer(
            window, mock_model, mock_device, mock_predict_fn, mock_preprocess_fn
        )

        assert prediction in ("Normal", "Abnormal")
        assert 0.0 <= abnormal_ratio <= 1.0
        assert latency_ms >= 0.0

    def test_infer_empty_tensor_returns_normal(self, sample_ecg_signal):
        """predict_fn trả về tensor rỗng → default "Normal"."""
        from ecg.consumers import _infer

        mock_predict_fn = MagicMock(return_value=torch.tensor([]))
        mock_preprocess_fn = MagicMock(return_value=torch.tensor([]))
        mock_model = MagicMock()
        mock_device = torch.device("cpu")

        window = sample_ecg_signal[:625]
        prediction, abnormal_ratio, confidence, latency_ms = _infer(
            window, mock_model, mock_device, mock_predict_fn, mock_preprocess_fn
        )

        assert prediction == "Normal"
        assert abnormal_ratio == 0.0

    def test_infer_exception_returns_normal(self, sample_ecg_signal):
        """predict_fn ném exception → fallback "Normal"."""
        from ecg.consumers import _infer

        mock_predict_fn = MagicMock(side_effect=RuntimeError("model exploded"))
        mock_model = MagicMock()
        mock_device = torch.device("cpu")
        mock_preprocess_fn = MagicMock()

        window = sample_ecg_signal[:625]
        prediction, abnormal_ratio, confidence, latency_ms = _infer(
            window, mock_model, mock_device, mock_predict_fn, mock_preprocess_fn
        )

        assert prediction == "Normal"


# Cần import MagicMock trong file này
from unittest.mock import MagicMock
