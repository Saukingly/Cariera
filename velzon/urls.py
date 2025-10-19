"""velzon URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from .views import MyPasswordChangeView, MyPasswordSetView
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # THIS IS THE CORRECTED LINE: Redirect to the JOURNEYS LIST page.
    path('', RedirectView.as_view(url='/apps/journeys/', permanent=False), name='home'),

    # Apps - This is where our main application URLs from apps/urls.py live.
    path('apps/', include('apps.urls')),
    
    # All Auth for login, logout, registration, etc.
    path('account/', include('allauth.urls')),

    # Custom password change views from the theme.
    path(
        "account/password/change/",
        login_required(MyPasswordChangeView.as_view()),
        name="account_change_password",
    ),
    path(
        "account/password/set/",
        login_required(MyPasswordSetView.as_view()),
        name="account_set_password",
    ),

    # The following are part of the original theme and can be removed later if not used.
    path('layouts/', include('layouts.urls')),
    path('components/', include('components.urls')),
    path('pages/', include('pages.urls')),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)