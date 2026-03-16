from django.urls import path

from . import consumers
from apps.messenger.routing import websocket_urlpatterns as chat_urlpatterns

websocket_urlpatterns = [
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
] + chat_urlpatterns
