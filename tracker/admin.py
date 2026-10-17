from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Account, Category, Transaction, Budget, RecurringTransaction, SavingsGoal, UserPresence


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'presence_status', 'last_seen')
    list_filter = DjangoUserAdmin.list_filter + ('is_active',)
    readonly_fields = DjangoUserAdmin.readonly_fields + ('last_seen',)

    @admin.display(description='Online', boolean=True)
    def presence_status(self, obj):
        try:
            seen = obj.presence.last_seen
        except UserPresence.DoesNotExist:
            seen = None
        return bool(obj.is_active and seen and seen >= timezone.now() - timedelta(minutes=5))

    @admin.display(description='Last seen', ordering='presence__last_seen')
    def last_seen(self, obj):
        try:
            return obj.presence.last_seen
        except UserPresence.DoesNotExist:
            return 'Never'


@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_seen')
    search_fields = ('user__username', 'user__email')
    ordering = ('-last_seen',)
    readonly_fields = ('user', 'last_seen')

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'type', 'starting_balance')
    list_filter = ('type',)
    search_fields = ('name', 'user__username')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'type', 'icon')
    list_filter = ('type',)
    search_fields = ('name', 'user__username')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('amount', 'type', 'category', 'account', 'date', 'user')
    list_filter = ('type', 'date')
    search_fields = ('note', 'user__username')

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'limit')

@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ('amount', 'type', 'category', 'frequency', 'next_due_date', 'user')
    list_filter = ('frequency', 'type')

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'target_amount', 'target_date', 'account')

