# apps/routing.py
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/interview/<uuid:session_id>/', consumers.InterviewConsumer.as_asgi()),
]  # ← NO COMMA HERE