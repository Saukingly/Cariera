# velzon/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

# Import the new project-level router
import velzon.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velzon.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    # Point the websocket key to our new project-level router
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            velzon.routing.application
        )
    ),
})