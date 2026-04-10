import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import TensorDataset, DataLoader
from sklearn.utils.class_weight import compute_class_weight
from scipy.signal import butter, filtfilt, find_peaks
from scipy.interpolate import interp1d

# Mô hình phân loại ECG
class ResidualBlock1D(nn.Module):
    def __init__(self, channels, kernel_size=5):
        super().__init__()
        padding = kernel_size // 2

        self.conv1 = nn.Conv1d(channels, channels, kernel_size, padding=padding)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size, padding=padding)
        self.conv3 = nn.Conv1d(channels, channels, kernel_size, padding=padding)

        self.relu = nn.ReLU(inplace=True)
        self.pool = nn.MaxPool1d(2)

    def forward(self, x):
        identity = self.pool(x)   # downsample skip path

        out = self.conv1(x)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.relu(out)
        out = self.conv3(out)

        out = self.pool(out)
        out = out + identity
        out = self.relu(out)

        return out


class ECG_CNN(nn.Module):
    def __init__(self, num_classes=5):
        super().__init__()

        # Input: (B, 1, 187)
        self.stem = nn.Conv1d(1, 32, kernel_size=5, padding=2)

        # 5 Residual Blocks
        self.res_blocks = nn.Sequential(
            ResidualBlock1D(32),
            ResidualBlock1D(32),
            ResidualBlock1D(32),
            ResidualBlock1D(32),
            ResidualBlock1D(32),
        )

        # Sau 5 lần pool: 187 → ~5
        self.fc1 = nn.Linear(32 * 5, 128)
        self.fc2 = nn.Linear(128, num_classes)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        # x: (B, 187)
        x = x.unsqueeze(1)          # (B, 1, 187)
        x = self.stem(x)            # (B, 32, 187)
        x = self.res_blocks(x)      # (B, 32, ~5)

        x = x.flatten(1)            # (B, 32*5)
        x = self.relu(self.fc1(x))
        x = self.fc2(x)

        return x


# Tiền xử lý
# ===== 1. Bandpass Filter =====
def bandpass_filter(signal, fs=125, lowcut=0.5, highcut=40, order=3):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    filtered = filtfilt(b, a, signal)
    return filtered


# ===== 2. Normalize =====
def normalize_signal(signal):
    mean = np.mean(signal)
    std = np.std(signal)
    return (signal - mean) / (std + 1e-8)


# ===== 3. Resize về 187 samples =====
def resize_beat(beat, target_len=187):
    x_old = np.linspace(0, 1, len(beat))
    x_new = np.linspace(0, 1, target_len)
    f = interp1d(x_old, beat, kind='linear')
    return f(x_new)


# ===== 4. Full preprocessing pipeline =====
def preprocess_ecg_signal(raw_signal, fs=125):

    # Filter
    filtered = bandpass_filter(raw_signal, fs)

    # Detect R-peaks
    peaks, _ = find_peaks(filtered, distance=fs*0.4)

    beats = []

    for peak in peaks:
        start = peak - int(0.3 * fs)
        end   = peak + int(0.4 * fs)

        if start >= 0 and end < len(filtered):
            beat = filtered[start:end]
            beat = resize_beat(beat, 187)
            beat = normalize_signal(beat)
            beats.append(beat)

    beats = np.array(beats)

    # Convert sang tensor (N, 1, 187)
    beats_tensor = torch.tensor(beats, dtype=torch.float32)

    return beats_tensor

# Dự đoán kết quả
def predict(raw_signal, model, device):
    beats = preprocess_ecg_signal(raw_signal)
    beats = beats.to(device)
    model.eval()
    with torch.no_grad():
        logits = model(beats)
        preds = torch.argmax(logits, dim=1)
    return preds

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Using device: {device}")    
# Khởi tạo mô hình
try:
    model = ECG_CNN(num_classes=5).to(device)
    ckpt = torch.load(r".\model\best_epoch_5_loss_0.1693.pth", map_location=torch.device('cpu'))

    model.load_state_dict(ckpt["model_state"])
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

