from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils import timezone

from .models import UserPresence


@staff_member_required
def user_overview(request):
    User = get_user_model()
    cutoff = timezone.now() - timedelta(minutes=5)
    users = User.objects.select_related('presence').order_by('-date_joined')
    online_ids = UserPresence.objects.filter(last_seen__gte=cutoff, user__is_active=True).values('user_id')
    context = {
        **admin.site.each_context(request),
        'title': 'User overview',
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
        'staff_users': User.objects.filter(is_staff=True).count(),
        'online_users': User.objects.filter(pk__in=online_ids).count(),
        'users': users[:100],
        'online_cutoff': cutoff,
    }
    return render(request, 'admin/user_overview.html', context)
