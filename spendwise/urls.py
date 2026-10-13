"""
URL configuration for spendwise project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.views.generic import RedirectView


class ConfiguredPasswordResetView(auth_views.PasswordResetView):
    def form_valid(self, form):
        smtp_configured = all((
            settings.EMAIL_HOST,
            settings.EMAIL_HOST_USER,
            settings.EMAIL_HOST_PASSWORD,
        ))
        if not settings.DEBUG and not smtp_configured:
            form.add_error(
                None,
                'Password reset email is not configured yet. Please contact support.',
            )
            return self.form_invalid(form)
        return super().form_valid(form)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RedirectView.as_view(pattern_name='login', permanent=False, query_string=True)),
    path('', include('tracker.urls')),
    path('oauth/', include('allauth.urls')),
    path('password_reset/', ConfiguredPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
