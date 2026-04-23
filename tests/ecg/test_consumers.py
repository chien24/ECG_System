"""
tests/ecg/test_consumers.py — kiểm thử ECGConsumer (WebSocket).

Dùng channels.testing.WebsocketCommunicator để test:
  - connect / disconnect
  - receive chunk hợp lệ (chưa đủ STEP_SIZE → echo)
  - receive stop signal
  - invalid JSON
  - chunk rỗng
  - chunk không hợp lệ (chuỗi ký tự)
  - model chưa sẵn sàng (mock _load_model trả về None)
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import torch
from channels.testing import WebsocketCommunicator

# Dùng InMemoryChannelLayer để test không cần Redis
TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@pytest.fixture(autouse=True)
def _use_inmemory_channel_layer(settings):
    """Áp CHANNEL_LAYERS cho toàn bộ test trong module."""
    settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS


def _make_app():
    """Tạo ASGI application với routing WebSocket."""
    from channels.routing import URLRouter
    from django.urls import re_path
    from ecg.consumers import ECGConsumer

    application = URLRouter([
        re_path(r"^ws/ecg/$", ECGConsumer.as_asgi()),
    ])
    return application


@pytest.mark.asyncio
class TestECGConsumerConnect:
    async def test_connect_accept(self):
        """Consumer phải chấp nhận kết nối."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        connected, subprotocol = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_disconnect_graceful(self):
        """Disconnect không raise exception."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()
        await communicator.disconnect()
        # Không có exception → pass


@pytest.mark.asyncio
class TestECGConsumerReceive:
    async def test_stop_signal_resets_state(self):
        """Gửi {stop: true} → nhận {stopped: true}."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        await communicator.send_json_to({"stop": True})
        response = await communicator.receive_json_from()

        assert response.get("stopped") is True
        await communicator.disconnect()

    async def test_invalid_json_returns_error(self):
        """Gửi text không phải JSON → nhận {error: ...}."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        await communicator.send_to(text_data="THIS IS NOT JSON {{{")
        response = await communicator.receive_json_from()

        assert "error" in response
        assert "JSON" in response["error"]
        await communicator.disconnect()

    async def test_empty_chunk_returns_error(self):
        """Gửi chunk rỗng → nhận {error: ...}."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        await communicator.send_json_to({"chunk": []})
        response = await communicator.receive_json_from()

        assert "error" in response
        assert "rỗng" in response["error"].lower() or "chunk" in response["error"].lower()
        await communicator.disconnect()

    async def test_invalid_chunk_type_returns_error(self):
        """Chunk chứa chuỗi ký tự → nhận {error: ...}."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        await communicator.send_json_to({"chunk": ["a", "b", "c"]})
        response = await communicator.receive_json_from()

        assert "error" in response
        await communicator.disconnect()

    async def test_model_not_ready_returns_error(self):
        """Khi model=None → {error: 'Mô hình AI chưa sẵn sàng.'}."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        with patch("ecg.consumers._load_model", return_value=(None, None, None, None)):
            await communicator.send_json_to({"chunk": [0.1, 0.2, 0.3]})
            response = await communicator.receive_json_from()

        assert "error" in response
        assert "chưa sẵn sàng" in response["error"]
        await communicator.disconnect()

    async def test_small_chunk_echoes_without_prediction(self):
        """
        Chunk nhỏ (< STEP_SIZE = 125 mẫu) → server echo chunk + samples_total,
        không có 'prediction' key (chưa predict).
        """
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        small_chunk = [float(i) for i in range(25)]  # 25 samples < 125

        # Mock model để chunk được xử lý (không bị dừng ở "model=None")
        mock_model = MagicMock()
        mock_device = MagicMock()
        mock_predict = MagicMock()
        mock_preprocess = MagicMock()

        with patch(
            "ecg.consumers._load_model",
            return_value=(mock_model, mock_device, mock_predict, mock_preprocess),
        ):
            await communicator.send_json_to({"chunk": small_chunk})
            response = await communicator.receive_json_from()

        assert "signal" in response
        assert response["signal"] == small_chunk
        assert "samples_total" in response
        # Chưa đủ để predict → không có key 'prediction'
        assert "prediction" not in response
        await communicator.disconnect()

    async def test_large_chunk_triggers_prediction(self):
        """
        Gửi đủ ≥ STEP_SIZE (125) mẫu → consumer gọi _infer và trả về prediction.
        Mock _infer để không cần model thật.
        """
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        # Gửi chunk 125 samples (= STEP_SIZE)
        big_chunk = [float(i % 100) / 100 for i in range(125)]

        mock_model = MagicMock()
        mock_device = MagicMock()
        mock_predict_fn = MagicMock()
        mock_preprocess_fn = MagicMock()

        with (
            patch(
                "ecg.consumers._load_model",
                return_value=(mock_model, mock_device, mock_predict_fn, mock_preprocess_fn),
            ),
            patch(
                "ecg.consumers._infer",
                return_value=("Normal", 0.05, 0.92, 15.0),
            ),
        ):
            await communicator.send_json_to({"chunk": big_chunk})
            response = await communicator.receive_json_from()

        assert "prediction" in response
        assert response["prediction"] in ("Normal", "Abnormal")
        assert "confidence" in response
        assert "abnormal_ratio" in response
        assert "latency_ms" in response
        assert "samples_total" in response
        await communicator.disconnect()

    async def test_response_format_keys(self):
        """Khi predict được, response phải có đầy đủ các key chuẩn."""
        app = _make_app()
        communicator = WebsocketCommunicator(app, "ws/ecg/")
        await communicator.connect()

        chunk = [float(i % 50) / 50 for i in range(125)]

        with (
            patch(
                "ecg.consumers._load_model",
                return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
            ),
            patch(
                "ecg.consumers._infer",
                return_value=("Abnormal", 0.35, 0.78, 22.5),
            ),
        ):
            await communicator.send_json_to({"chunk": chunk})
            response = await communicator.receive_json_from()

        required_keys = {"signal", "prediction", "confidence", "abnormal_ratio", "latency_ms", "samples_total"}
        assert required_keys.issubset(response.keys())
        await communicator.disconnect()
