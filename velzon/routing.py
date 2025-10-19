# velzon/routing.py
from django.urls import re_path
from channels.routing import URLRouter
import apps.routing

application = URLRouter([
    re_path(r"^apps/", URLRouter(
        apps.routing.websocket_urlpatterns
    ))
])  # ← NO COMMA HERE