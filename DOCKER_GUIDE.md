# Hướng dẫn Deploy Django Channels với Docker

Chào bạn! Tôi đã tạo xong các file cấu hình cần thiết để Dockerize project Django của bạn. Dưới đây là tóm tắt và hướng dẫn sử dụng.

## 1. Các file đã tạo
- **Dockerfile**: Cấu hình build image dựa trên `python:3.10-slim`.
- **.dockerignore**: Loại bỏ các file rác, `venv`, và `db.sqlite3` khi build để tối ưu dung lượng.
- **docker-compose.yml**: Quản lý song song server Web và Redis (cần thiết cho WebSocket channel layer).

## 2. Hướng dẫn Build & Run

### Cách 1: Sử dụng Docker thuần (Chỉ web server)
Dùng lệnh này nếu bạn chỉ muốn chạy container của Django.

1.  **Build image:**
    ```bash
    docker build -t ecg_app .
    ```
2.  **Run container:**
    ```bash
    docker run -p 8000:8000 ecg_app
    ```

### Cách 2: Sử dụng Docker Compose (Khuyên dùng)
Dùng lệnh này để chạy cả Web và Redis cùng một lúc.

1.  **Chạy dịch vụ:**
    ```bash
    docker-compose up --build
    ```
2.  **Chạy ngầm (Background):**
    ```bash
    docker-compose up -d
    ```

## 3. Một số lưu ý quan trọng

### Kích thước Image (ML Dependencies)
Vì project của bạn có sử dụng `torch`, `numpy`, `pandas`, image build ra sẽ khá nặng (có thể hơn 2GB). Đây là điều bình thường đối với các project Deep Learning. Việc dùng bản `slim` đã giúp giảm đáng kể so với bản `full`.

### Cấu hình Redis cho WebSocket
Hiện tại project của bạn đang dùng `InMemoryChannelLayer`. Để dùng Redis trong môi trường Docker, bạn nên:
1. Cài đặt thêm: `pip install channels-redis`.
2. Sửa file `settings.py`:
   ```python
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("redis", 6379)], # "redis" là tên service trong compose
           },
       },
   }
   ```

### Migrate Database
Sau khi container khởi động, nếu là lần đầu, bạn có thể cần chạy migrate:
```bash
docker exec -it <container_id> python manage.py migrate
```
