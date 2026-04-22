# 🫀 Real-time ECG Analysis System

Hệ thống phân tích điện tim (ECG) thời gian thực sử dụng Deep Learning, xây dựng trên nền tảng Django với hỗ trợ WebSocket qua Django Channels & Daphne.

---

## ✨ Tính năng

- **Phân tích ECG thời gian thực** qua WebSocket
- **Phát hiện loạn nhịp tim** bằng mô hình Deep Learning (PyTorch)
- **Xác thực người dùng** với hệ thống đăng nhập/đăng ký riêng
- **Giao diện web** trực quan để theo dõi tín hiệu ECG
- **Channel Layer** linh hoạt: hỗ trợ cả InMemory (dev) và Redis (production)

---

## 🛠️ Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Web Framework | Django 5.0.6 |
| ASGI Server | Daphne 4.2.1 |
| WebSocket | Django Channels 4.3.2 |
| Channel Layer | Redis (production) / InMemory (dev) |
| Deep Learning | PyTorch 2.3.1 |
| Containerization | Docker & Docker Compose |

---

## 📁 Cấu trúc dự án

```
ecg_system/
├── ecg/                    # App chính: ECG processing & WebSocket
│   ├── consumers.py        # WebSocket consumer
│   ├── routing.py          # WebSocket URL routing
│   ├── views.py            # HTTP views
│   ├── models.py           # Database models
│   ├── templates/          # HTML templates
│   └── static/             # CSS, JS, assets
├── ecg_system/             # Cấu hình Django project
│   ├── settings.py         # Settings (auto-switch Redis/InMemory)
│   ├── asgi.py             # ASGI entry point (HTTP + WebSocket)
│   └── urls.py             # URL routing chính
├── users/                  # App xác thực người dùng
├── model/                  # File model AI (.pth)
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── requirements.txt
```

---

## 🚀 Hướng dẫn Cài đặt & Chạy

### Yêu cầu

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) đã được cài đặt và đang chạy.

### Chạy với Docker Compose (Khuyên dùng)

Đây là cách đơn giản nhất, tự động khởi động cả web server lẫn Redis.

```bash
# 1. Clone/tải về project và di chuyển vào thư mục ecg_system
cd ecg_system

# 2. Build image và khởi động tất cả dịch vụ
docker-compose up --build

# Truy cập tại: http://localhost:8000
```

Để chạy nền (background):
```bash
docker-compose up -d
```

Để dừng:
```bash
docker-compose down
```

### Chạy lần đầu: Migrate Database

Sau khi container đã khởi động, mở terminal khác và chạy:
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

---

## ⚙️ Cấu hình

### Biến môi trường

| Biến | Giá trị mặc định | Mô tả |
|---|---|---|
| `USE_REDIS` | `1` (trong Docker) | `1` = dùng Redis, `0` = dùng InMemory |
| `DJANGO_SETTINGS_MODULE` | `ecg_system.settings` | Module settings Django |

### Channel Layer (settings.py)

Hệ thống tự động chọn channel layer phù hợp dựa vào biến môi trường `USE_REDIS`:

- **`USE_REDIS=1`** (Docker Compose): Dùng `RedisChannelLayer` — đảm bảo WebSocket hoạt động đúng trong production.
- **`USE_REDIS=0`** (local dev): Dùng `InMemoryChannelLayer` — không cần Redis, tiện cho phát triển.

---

## 🔌 WebSocket API

WebSocket endpoint được cấu hình tại `ecg/routing.py`.

Kết nối:
```
ws://localhost:8000/ws/ecg/<room_name>/
```

---

## 🐳 Chi tiết Docker

### Dockerfile

- Base image: `python:3.10-slim` (tối ưu dung lượng)
- Cài đặt system dependencies (`build-essential`, `libpq-dev`)
- Cài Python packages từ `requirements.txt`
- Run server bằng **Daphne** (ASGI) tại port `8000`

### docker-compose.yml

Bao gồm 2 services:

| Service | Image | Port | Mô tả |
|---|---|---|---|
| `web` | Build từ Dockerfile | `8000:8000` | Django + Daphne |
| `redis` | `redis:alpine` | `6379:6379` | Channel Layer backend |

> Service `web` chỉ khởi động sau khi Redis đã healthy (`healthcheck`).

---

## 📦 Dependencies chính

```
django==5.0.6
channels==4.3.2
channels-redis==4.3.0
daphne==4.2.1
torch==2.3.1
torchvision==0.18.1
pandas==2.2.2
scikit-learn==1.5.2
```

> ⚠️ **Lưu ý**: Do có `torch` và `torchvision`, image Docker sẽ khá lớn (~2-3 GB). Quá trình build lần đầu sẽ mất vài phút, đây là bình thường.
