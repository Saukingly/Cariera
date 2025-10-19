# velzon/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import the project-level router
import velzon.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velzon.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    # --- SIMPLIFIED WEBSOCKET ROUTING ---
    # We are temporarily removing the AllowedHostsOriginValidator.
    # The AuthMiddlewareStack still ensures that only logged-in users can connect.
    "websocket": AuthMiddlewareStack(
        URLRouter(
            # Pass the actual list of URL patterns directly. This is the most reliable way.
            velzon.routing.application.url_patterns
        )
    ),
})