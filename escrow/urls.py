from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_of_service, name='terms'),
    path('webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('admin/', admin.site.urls),
    path('provider/<int:provider_id>/', views.provider_detail, name='provider_detail'),
    path('momo-webhook/', views.momo_sms_webhook, name='momo_webhook'),
]
