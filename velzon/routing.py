# velzon/routing.py

from django.urls import path
from channels.routing import URLRouter
import apps.routing

# This is the project-level router for WebSockets.
# It's like your project's urls.py, but for WebSockets.
application = URLRouter([
    # This line says: "For any WebSocket connection that starts with 'apps/',
    # pass the rest of the URL to the router defined in apps.routing."
    path("apps/", URLRouter(
        apps.routing.websocket_urlpatterns
    ))
])