from django.conf import settings


def social_login_providers(_request):
    return {
        'google_login_enabled': bool(
            settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
        ),
    }
