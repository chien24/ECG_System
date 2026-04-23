# 🫀 Real-time ECG Analysis System

Hệ thống phân tích điện tim (ECG) thời gian thực sử dụng **Deep Learning**, xây dựng trên nền tảng **Django ASGI** với hỗ trợ **WebSocket** qua Django Channels & Daphne. Hệ thống được deploy lên **Render** dưới dạng Docker container đơn lẻ.

---

## ✨ Tính năng

- 📡 **Phân tích ECG thời gian thực** qua WebSocket
- 🧠 **Phát hiện loạn nhịp tim** bằng mô hình Deep Learning (PyTorch)
- 🔐 **Xác thực người dùng** với hệ thống đăng nhập / đăng ký riêng
- 📊 **Giao diện web** trực quan để theo dõi tín hiệu ECG
- ☁️ **Triển khai trên Render** — PostgreSQL + Docker container
- ⚡ **Channel Layer linh hoạt**: Redis (Docker Compose) hoặc InMemory (Render free tier)

---

## 🛠️ Công nghệ sử dụng

| Thành phần        | Công nghệ                                |
|-------------------|------------------------------------------|
| Web Framework     | Django 5.0.6                             |
| ASGI Server       | Daphne 4.2.1                             |
| WebSocket         | Django Channels 4.3.2                    |
| Channel Layer     | InMemory (Render) / Redis (Docker local) |
| Deep Learning     | PyTorch 2.3.1 + torchvision + torchaudio |
| Database          | PostgreSQL (Render) / SQLite (local)     |
| Static Files      | WhiteNoise 6.9.0                         |
| Containerization  | Docker (single container)                |
| PaaS Deployment   | [Render](https://render.com)             |

---

## 📁 Cấu trúc dự án

```
ecg_system/
├── ecg/                    # App chính: ECG processing & WebSocket
│   ├── consumers.py        # WebSocket consumer (xử lý ECG real-time)
│   ├── routing.py          # WebSocket URL routing
│   ├── views.py            # HTTP views
│   ├── models.py           # Database models
│   ├── templates/          # HTML templates
│   └── static/             # CSS, JS, assets
├── ecg_system/             # Cấu hình Django project
│   ├── settings.py         # Settings (auto-switch Redis/InMemory, DB)
│   ├── asgi.py             # ASGI entry point (HTTP + WebSocket)
│   └── urls.py             # URL routing chính
├── users/                  # App xác thực người dùng
├── model/                  # File model AI (.pth)
├── Dockerfile              # Production Docker image (python:3.10-slim)
├── docker-compose.yml      # Local dev: web + Redis
├── start.sh                # Container startup script (collectstatic → migrate → superuser → daphne)
├── .env                    # Biến môi trường (KHÔNG commit file thật)
├── .dockerignore
└── requirements.txt
```

---

## 🚀 Hướng dẫn cài đặt & Chạy

### ▶️ Cách 1: Chạy local với Docker Compose (Khuyên dùng)

Tự động khởi động cả Django (Daphne) lẫn Redis trong một lệnh.

**Yêu cầu:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) đã cài và đang chạy.

```bash
# 1. Di chuyển vào thư mục ecg_system
cd ecg_system

# 2. Build image và khởi động tất cả services
docker-compose up --build

# Truy cập tại: http://localhost:8000
```

Chạy nền:
```bash
docker-compose up -d --build
```

Dừng:
```bash
docker-compose down
```

> ⚠️ Với Docker Compose, `migrate` và `collectstatic` chạy tự động. Không cần chạy thủ công.  
> Để tạo superuser khi dùng Docker Compose:
> ```bash
> docker-compose exec web python manage.py createsuperuser
> ```

---

### ▶️ Cách 2: Chạy local không dùng Docker

**Yêu cầu:** Python 3.10+, (tuỳ chọn) Redis nếu muốn dùng `USE_REDIS=1`.

```bash
# 1. Tạo và kích hoạt virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo file .env (xem mẫu bên dưới)
copy .env .env.local          # Đổi tên hoặc tạo mới

# 4. Chạy migrations
python manage.py migrate

# 5. Tạo superuser
python manage.py createsuperuser

# 6. Khởi động server (Daphne ASGI)
daphne -b 0.0.0.0 -p 8000 ecg_system.asgi:application
```

---

## ⚙️ Cấu hình biến môi trường

Tạo file `.env` trong thư mục gốc (`ecg_system/`) với nội dung sau:

```env
# ── Django ─────────────────────────────────────────────────────
# Tạo secret key: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=django-insecure-replace-this-with-a-real-secret-key
DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1 your-app.onrender.com

# ── Django Admin Superuser (tự động tạo lúc khởi động container) ──
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=YourStrongPassword123!

# ── Database ────────────────────────────────────────────────────
# PostgreSQL (Render): postgresql://USER:PASS@HOST:PORT/DBNAME
# Để trống để dùng SQLite (local dev)
DATABASE_URL=

# ── Redis / Channels ───────────────────────────────────────────
USE_REDIS=0          # 1 = Redis, 0 = InMemory (đủ cho Render free tier)
REDIS_URL=redis://localhost:6379

# ── Server port ────────────────────────────────────────────────
PORT=8000            # Render tự inject $PORT — KHÔNG set trên Render
```

> 🔒 **KHÔNG BAO GIỜ commit file `.env` thật lên Git.**  
> Thêm `.env` vào `.gitignore` nếu chưa có.

---

## ☁️ Deploy lên Render

### Bước 1: Chuẩn bị

1. Push code lên GitHub (đảm bảo `.env` đã bị gitignore).
2. Tạo **PostgreSQL Database** trên Render → lấy **Internal Database URL**.

### Bước 2: Tạo Web Service trên Render

| Trường          | Giá trị                             |
|-----------------|-------------------------------------|
| Environment     | Docker                              |
| Branch          | `main`                              |
| Dockerfile path | `./Dockerfile`                      |
| Start command   | *(để trống — Dockerfile dùng CMD)* |

### Bước 3: Cấu hình Environment Variables trên Render Dashboard

| Biến                       | Giá trị                        |
|----------------------------|-------------------------------|
| `SECRET_KEY`               | *(generate key mạnh)*         |
| `DEBUG`                    | `False`                       |
| `DJANGO_ALLOWED_HOSTS`     | `your-app.onrender.com`       |
| `DATABASE_URL`             | *(Internal URL từ Render DB)* |
| `USE_REDIS`                | `0`                           |
| `DJANGO_SUPERUSER_USERNAME`| `admin`                       |
| `DJANGO_SUPERUSER_EMAIL`   | `admin@example.com`           |
| `DJANGO_SUPERUSER_PASSWORD`| *(mật khẩu mạnh)*            |

> `PORT` **KHÔNG cần set** — Render tự inject.

### Bước 4: Deploy

Nhấn **Deploy** — Render sẽ tự động:
1. Build Docker image
2. Chạy `start.sh`:
   - `collectstatic` → `migrate` → tạo superuser (nếu chưa có) → khởi động Daphne

---

## 🔄 Startup Script (`start.sh`)

Mỗi lần container khởi động, `start.sh` thực hiện theo thứ tự:

```
[1/4] collectstatic   — copy static files vào STATIC_ROOT (WhiteNoise serve)
[2/4] migrate         — áp dụng database migrations
[3/4] createsuperuser — tạo admin nếu chưa tồn tại (idempotent, không lỗi)
[4/4] daphne          — khởi động ASGI server tại 0.0.0.0:$PORT
```

Bước tạo superuser dùng Python để kiểm tra trước, **không gây lỗi** khi user đã tồn tại.

---

## 🔌 WebSocket API

WebSocket endpoint cấu hình tại `ecg/routing.py`.

```
# Development (HTTP)
ws://localhost:8000/ws/ecg/<room_name>/

# Production (HTTPS/Render)
wss://your-app.onrender.com/ws/ecg/<room_name>/
```

> Script frontend tự động chọn `ws://` hoặc `wss://` dựa vào `window.location.protocol`.

---

## 🐳 Chi tiết Docker

### Dockerfile

- **Base image**: `python:3.10-slim` (Debian Bookworm)
- **System deps**: `gcc`, `libgomp1` (PyTorch/OpenMP), `libpq-dev` (PostgreSQL)
- **Security**: Chạy bằng non-root user `appuser`
- **Static files**: Thư mục `/app/staticfiles` tạo sẵn với đúng quyền
- **Startup**: `CMD ["sh", "/app/start.sh"]`

### docker-compose.yml (local dev)

| Service | Image           | Port      | Mô tả                  |
|---------|-----------------|-----------|------------------------|
| `web`   | Build từ local  | `8000`    | Django + Daphne        |
| `redis` | `redis:alpine`  | `6379`    | Channel Layer backend  |

> `web` chỉ khởi động sau khi Redis đã healthy (healthcheck `redis-cli ping`).

---

## 📦 Dependencies chính

```
# Deep Learning
torch==2.3.1 | torchvision==0.18.1 | torchaudio==2.3.1

# Django & WebSocket
django==5.0.6 | channels==4.3.2 | daphne==4.2.1

# Database
psycopg2-binary==2.9.9 | dj-database-url==2.1.0

# Static Files
whitenoise==6.9.0

# Data Science
numpy | pandas | scikit-learn | scipy | matplotlib | seaborn
```

> ⚠️ Do có `torch` và `torchvision`, image Docker sẽ khá lớn (~2–3 GB). Build lần đầu mất vài phút — hoàn toàn bình thường.

---

## 🗂️ Channel Layer

| Môi trường       | Layer               | Cấu hình         |
|------------------|---------------------|------------------|
| Local (Docker Compose) | `RedisChannelLayer` | `USE_REDIS=1`  |
| Render free tier | `InMemoryChannelLayer` | `USE_REDIS=0` |

`settings.py` tự động chọn dựa vào biến `USE_REDIS`.

> InMemory layer đủ dùng cho Render free tier (single instance). Nếu cần scale nhiều worker, chuyển sang Redis.
