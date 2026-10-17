from datetime import timedelta

from django.utils import timezone

from .models import UserPresence


class UserPresenceMiddleware:
    """Record authenticated activity, throttled to one database write per minute."""
    update_interval = timedelta(minutes=1)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            previous = UserPresence.objects.filter(user_id=user.pk).only('last_seen').first()
            if previous is None or now - previous.last_seen >= self.update_interval:
                UserPresence.objects.update_or_create(user_id=user.pk, defaults={'last_seen': now})
        return self.get_response(request)
