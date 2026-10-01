"""URL configuration for maya_project project."""

from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse, FileResponse, Http404
from django.views.generic import TemplateView
from django.conf import settings
from pathlib import Path
from django.conf.urls.static import static

# Client klasörü
CLIENT_DIR = Path(settings.BASE_DIR) / 'client'


def serve_file(request, filename='index.html'):
    """Client klasöründen dosya sun."""
    file_path = CLIENT_DIR / filename
    
    if not file_path.exists():
        raise Http404()
    
    # Content type belirle
    content_types = {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.svg': 'image/svg+xml',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.ico': 'image/x-icon',
    }
    content_type = content_types.get(file_path.suffix, 'application/octet-stream')
    
    return FileResponse(open(file_path, 'rb'), content_type=content_type)


def serve_asset(request, filename):
    """Assets klasöründen dosya sun."""
    file_path = CLIENT_DIR / 'assets' / filename
    
    if not file_path.exists():
        raise Http404()
    
    content_types = {
        '.svg': 'image/svg+xml',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
    }
    content_type = content_types.get(file_path.suffix, 'application/octet-stream')
    
    return FileResponse(open(file_path, 'rb'), content_type=content_type)


urlpatterns = [
    # Ana sayfa - Maya chatbot
    path('', lambda r: serve_file(r, 'index.html'), name='home'),
    
    # Static dosyalar
    path('styles.css', lambda r: serve_file(r, 'styles.css')),
    path('app.js', lambda r: serve_file(r, 'app.js')),
    path('assets/<str:filename>', serve_asset),
    
    # Admin ve API
    path('admin/', admin.site.urls),
    path('api/', include('chatbot.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)