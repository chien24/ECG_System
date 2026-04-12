"""
ECG WebSocket Consumer – xử lý real-time ECG stream qua Django Channels.

Pipeline:
  receive signal (list[float])
      → Streaming Simulator (chunk 25 samples)
      → Rolling Buffer (5 s = 625 samples)
      → Sliding Window (5 s, step 1 s)
      → preprocess_ecg_signal() + predict()  [từ model/model.py]
      → Post-processing (abnormal_ratio threshold)
      → send JSON qua WebSocket
"""

import asyncio
import json
import logging

import numpy as np
import torch
import torch.nn.functional as F
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# ── Hằng số pipeline ─────────────────────────────────────────────────────────
FS = 125              # Tần số lấy mẫu (Hz)
CHUNK_SIZE = 25       # Cỡ chunk mỗi lần gửi (~0.2 s)
WINDOW_SIZE = 5 * FS  # Buffer / window 5 giây = 625 mẫu
STEP_SIZE = FS        # Bước sliding window = 1 giây
ABNORMAL_THRESHOLD = 0.20  # > 20 % beats bất thường → kết luận Bất thường

# ── Lazy-import model để tránh import vòng ───────────────────────────────────
_model = None
_device = None
_predict_fn = None
_preprocess_fn = None


def _load_model():
    """Import model một lần duy nhất, tái dùng sau đó."""
    global _model, _device, _predict_fn, _preprocess_fn
    if _model is None:
        try:
            from model.model import model, device, predict, preprocess_ecg_signal
            _model = model
            _device = device
            _predict_fn = predict
            _preprocess_fn = preprocess_ecg_signal
        except Exception as exc:
            logger.error("Không thể load model: %s", exc)
    return _model, _device, _predict_fn, _preprocess_fn


# ── Helper: tính confidence bằng softmax ─────────────────────────────────────
def _compute_confidence(raw_signal_window, model, device, preprocess_fn):
    """
    Trả về confidence trung bình (softmax max-class) trên cửa sổ hiện tại.
    Trả về 0.0 nếu không tính được.
    """
    try:
        beats = preprocess_fn(raw_signal_window)
        if beats is None or len(beats) == 0:
            return 0.0
        beats = beats.to(device)
        model.eval()
        with torch.no_grad():
            logits = model(beats)                  # (N, 5)
            probs = F.softmax(logits, dim=1)       # (N, 5)
            confidence = probs.max(dim=1).values.mean().item()
        return round(confidence, 4)
    except Exception:
        return 0.0


class ECGConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer cho real-time ECG analysis.

    Client gửi JSON:
        { "signal": [float, float, ...] }

    Server push liên tục JSON:
        {
            "signal":         [float, ...],   // chunk hiện tại
            "prediction":     "Normal" | "Abnormal",
            "confidence":     float,
            "abnormal_ratio": float
        }
    """

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def connect(self):
        await self.accept()
        logger.info("ECGConsumer: kết nối WebSocket được chấp nhận.")

    async def disconnect(self, code):
        logger.info("ECGConsumer: ngắt kết nối (code=%s).", code)

    # ── Nhận dữ liệu từ client ────────────────────────────────────────────────
    async def receive(self, text_data=None, bytes_data=None):
        """Nhận tín hiệu ECG và bắt đầu pipeline streaming."""
        try:
            payload = json.loads(text_data or "{}")
            signal_list = payload.get("signal", [])

            if not signal_list:
                await self._send_error("Không nhận được dữ liệu tín hiệu ECG.")
                return

            raw_signal = np.array(signal_list, dtype=np.float64)
            await self._run_pipeline(raw_signal)

        except json.JSONDecodeError:
            await self._send_error("Dữ liệu JSON không hợp lệ.")
        except Exception as exc:
            logger.exception("ECGConsumer.receive lỗi: %s", exc)
            await self._send_error(f"Lỗi xử lý: {exc}")

    # ── Pipeline chính ────────────────────────────────────────────────────────
    async def _run_pipeline(self, raw_signal: np.ndarray):
        """
        Stream từng chunk qua buffer → sliding window → model → WebSocket.
        """
        model, device, predict_fn, preprocess_fn = _load_model()

        if model is None or predict_fn is None or preprocess_fn is None:
            await self._send_error("Mô hình AI chưa sẵn sàng. Vui lòng thử lại sau.")
            return

        buffer: list[float] = []
        samples_since_last_predict = 0
        total_samples = len(raw_signal)

        # ── Chia tín hiệu thành các chunk nhỏ ────────────────────────────────
        for chunk_start in range(0, total_samples, CHUNK_SIZE):
            chunk = raw_signal[chunk_start: chunk_start + CHUNK_SIZE].tolist()
            if not chunk:
                break

            # 1. Nạp chunk vào buffer
            buffer.extend(chunk)

            # 2. Giữ chỉ 5 giây gần nhất
            if len(buffer) > WINDOW_SIZE:
                buffer = buffer[-WINDOW_SIZE:]

            samples_since_last_predict += len(chunk)

            # 3. Cứ mỗi STEP_SIZE mẫu (1 s) → dự đoán một lần
            if samples_since_last_predict >= STEP_SIZE and len(buffer) >= CHUNK_SIZE:
                samples_since_last_predict = 0

                window_np = np.array(buffer, dtype=np.float64)
                prediction, abnormal_ratio, confidence = await asyncio.to_thread(
                    self._infer,
                    window_np, model, device, predict_fn, preprocess_fn,
                )

                await self.send(text_data=json.dumps({
                    "signal":         chunk,
                    "prediction":     prediction,
                    "confidence":     confidence,
                    "abnormal_ratio": abnormal_ratio,
                }))

            # 4. Mô phỏng real-time theo tần số lấy mẫu
            await asyncio.sleep(len(chunk) / FS)

        # ── Kết thúc stream ───────────────────────────────────────────────────
        await self.send(text_data=json.dumps({"done": True}))

    # ── Inference (chạy trong thread pool) ────────────────────────────────────
    @staticmethod
    def _infer(window_np, model, device, predict_fn, preprocess_fn):
        """
        Tính prediction, abnormal_ratio và confidence cho cữa sổ hiện tại.
        Hàm này được gọi trong thread riêng qua asyncio.to_thread().
        """
        try:
            preds_tensor = predict_fn(window_np, model, device)

            if preds_tensor is None or len(preds_tensor) == 0:
                return "Normal", 0.0, 0.0

            preds_np = preds_tensor.detach().cpu().numpy()
            total_beats = len(preds_np)
            abnormal_beats = int(np.sum(preds_np != 0))
            abnormal_ratio = round(abnormal_beats / total_beats, 4) if total_beats else 0.0

            prediction = "Abnormal" if abnormal_ratio > ABNORMAL_THRESHOLD else "Normal"

            # Confidence = softmax max-class trung bình
            confidence = _compute_confidence(window_np, model, device, preprocess_fn)

            return prediction, abnormal_ratio, confidence

        except Exception as exc:
            logger.warning("ECGConsumer._infer lỗi: %s", exc)
            return "Normal", 0.0, 0.0

    # ── Tiện ích ──────────────────────────────────────────────────────────────
    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({"error": message}))
