import os
import django

# Set Django settings FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velzon.settings')

# Initialize Django BEFORE importing any Django models
django.setup()

# NOW import Django and Channels stuff
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

# Get Django ASGI app
django_asgi_app = get_asgi_application()

# Import routing AFTER django.setup()
import apps.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                apps.routing.websocket_urlpatterns
            )
        )
    ),
})