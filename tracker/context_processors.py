from django.conf import settings


def social_login_providers(_request):
    return {
        'google_login_enabled': bool(
            settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
        ),
        'apple_login_enabled': bool(
            settings.APPLE_OAUTH_CLIENT_ID
            and settings.APPLE_OAUTH_KEY_ID
            and settings.APPLE_OAUTH_TEAM_ID
            and settings.APPLE_OAUTH_PRIVATE_KEY
        ),
    }
