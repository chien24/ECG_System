"""
ASGI config for ecg_system project – hỗ trợ cả HTTP và WebSocket (Django Channels).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecg_system.settings')

# Phải gọi get_asgi_application() TRƯỚC khi import Channels routing
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from ecg.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
