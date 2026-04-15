"""
ECG WebSocket Consumer – kiến trúc streaming realtime thật.

Pipeline (per chunk):
  receive chunk (list[float])  ← gửi từ Frontend mỗi ~0.2s
      → Rolling Buffer (5s = 625 samples)
      → Predict nếu đủ STEP_SIZE mẫu mới
      → send JSON ngay lập tức

Không còn vòng lặp for xử lý toàn bộ dataset.
Không còn asyncio.sleep.
"""

import json
import logging
import time

import numpy as np
import torch
import torch.nn.functional as F
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# ── Hằng số pipeline ─────────────────────────────────────────────────────────
FS               = 125          # Tần số lấy mẫu (Hz)
CHUNK_SIZE       = 25           # Số mẫu mỗi chunk (~0.2s)
WINDOW_SIZE      = 5 * FS       # Buffer 5 giây = 625 mẫu
STEP_SIZE        = FS           # Bước dự đoán = 1 giây (125 mẫu)
ABNORMAL_THRESHOLD = 0.20       # > 20% beats bất thường → Bất thường

# ── Lazy-load model ───────────────────────────────────────────────────────────
_model       = None
_device      = None
_predict_fn  = None
_preprocess_fn = None


def _load_model():
    """Import model một lần duy nhất, tái dùng sau đó."""
    global _model, _device, _predict_fn, _preprocess_fn
    if _model is None:
        try:
            from model.model import model, device, predict, preprocess_ecg_signal
            _model        = model
            _device       = device
            _predict_fn   = predict
            _preprocess_fn = preprocess_ecg_signal
        except Exception as exc:
            logger.error("Không thể load model: %s", exc)
    return _model, _device, _predict_fn, _preprocess_fn


# ── Helpers ───────────────────────────────────────────────────────────────────
def _compute_confidence(window_np, model, device, preprocess_fn):
    """Trả về confidence trung bình (softmax max-class). Trả về 0.0 nếu lỗi."""
    try:
        beats = preprocess_fn(window_np)
        if beats is None or len(beats) == 0:
            return 0.0
        beats = beats.to(device)
        model.eval()
        with torch.no_grad():
            logits = model(beats)
            probs  = F.softmax(logits, dim=1)
            confidence = probs.max(dim=1).values.mean().item()
        return round(confidence, 4)
    except Exception:
        return 0.0


def _infer(window_np, model, device, predict_fn, preprocess_fn):
    """
    Tính prediction, abnormal_ratio và confidence cho cửa sổ hiện tại.
    Chạy đồng bộ (sẽ được gọi qua asyncio.to_thread).
    """
    try:
        t0 = time.perf_counter()

        preds_tensor = predict_fn(window_np, model, device)
        if preds_tensor is None or len(preds_tensor) == 0:
            return "Normal", 0.0, 0.0, 0.0

        preds_np      = preds_tensor.detach().cpu().numpy()
        total_beats   = len(preds_np)
        abnormal_beats = int(np.sum(preds_np != 0))
        abnormal_ratio = round(abnormal_beats / total_beats, 4) if total_beats else 0.0
        prediction     = "Abnormal" if abnormal_ratio > ABNORMAL_THRESHOLD else "Normal"
        confidence     = _compute_confidence(window_np, model, device, preprocess_fn)

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return prediction, abnormal_ratio, confidence, latency_ms

    except Exception as exc:
        logger.warning("_infer lỗi: %s", exc)
        return "Normal", 0.0, 0.0, 0.0


# ── Consumer ─────────────────────────────────────────────────────────────────
class ECGConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer – streaming realtime thật.

    Client gửi nhiều lần, mỗi lần 1 chunk nhỏ:
        { "chunk": [float, ...] }

    Hoặc gửi tín hiệu dừng:
        { "stop": true }

    Server trả về ngay sau mỗi chunk (nếu đủ dữ liệu để predict):
        {
            "signal":         [float, ...],
            "prediction":     "Normal" | "Abnormal",
            "confidence":     float,
            "abnormal_ratio": float,
            "latency_ms":     float,
            "samples_total":  int
        }
    """

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self):
        await self.accept()
        self._reset_state()
        logger.info("ECGConsumer: WebSocket kết nối chấp nhận.")

    async def disconnect(self, code):
        logger.info("ECGConsumer: ngắt kết nối (code=%s).", code)

    def _reset_state(self):
        """Khởi tạo / reset trạng thái streaming cho session mới."""
        self._buffer: list[float] = []          # Rolling buffer tối đa 5s
        self._samples_since_predict: int = 0    # Đếm mẫu kể từ lần predict gần nhất
        self._samples_total: int = 0            # Tổng mẫu đã nhận

    # ── Nhận chunk từ client ──────────────────────────────────────────────────

    async def receive(self, text_data=None, bytes_data=None):
        """
        Nhận 1 chunk nhỏ từ Frontend → xử lý ngay → trả kết quả ngay.
        Không có sleep, không có vòng lặp toàn bộ dataset.
        """
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            await self._send_error("JSON không hợp lệ.")
            return

        # ── Tín hiệu stop / reset ─────────────────────────────────────────
        if payload.get("stop"):
            self._reset_state()
            await self.send(text_data=json.dumps({"stopped": True}))
            logger.info("ECGConsumer: client yêu cầu dừng streaming.")
            return

        # ── Nhận chunk dữ liệu ────────────────────────────────────────────
        chunk = payload.get("chunk", [])
        if not chunk:
            await self._send_error("Chunk rỗng.")
            return

        if not isinstance(chunk, list) or not all(isinstance(v, (int, float)) for v in chunk):
            await self._send_error("Chunk không hợp lệ (phải là list số thực).")
            return

        model, device, predict_fn, preprocess_fn = _load_model()
        if model is None:
            await self._send_error("Mô hình AI chưa sẵn sàng.")
            return

        # ── Cập nhật rolling buffer ────────────────────────────────────────
        self._buffer.extend(chunk)
        self._samples_since_predict += len(chunk)
        self._samples_total += len(chunk)

        # Giữ chỉ WINDOW_SIZE (5s) mẫu gần nhất
        if len(self._buffer) > WINDOW_SIZE:
            self._buffer = self._buffer[-WINDOW_SIZE:]

        # ── Chỉ predict khi tích lũy đủ STEP_SIZE mẫu mới ────────────────
        if self._samples_since_predict < STEP_SIZE or len(self._buffer) < CHUNK_SIZE:
            # Chưa đủ → chỉ echo chunk để chart vẫn vẽ realtime
            await self.send(text_data=json.dumps({
                "signal":        chunk,
                "samples_total": self._samples_total,
            }))
            return

        # ── Inference trong thread pool (không block event loop) ───────────
        self._samples_since_predict = 0
        window_np = np.array(self._buffer, dtype=np.float64)

        import asyncio
        prediction, abnormal_ratio, confidence, latency_ms = await asyncio.to_thread(
            _infer, window_np, model, device, predict_fn, preprocess_fn
        )

        await self.send(text_data=json.dumps({
            "signal":         chunk,
            "prediction":     prediction,
            "confidence":     confidence,
            "abnormal_ratio": abnormal_ratio,
            "latency_ms":     latency_ms,
            "samples_total":  self._samples_total,
        }))

    # ── Tiện ích ──────────────────────────────────────────────────────────────

    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({"error": message}))
