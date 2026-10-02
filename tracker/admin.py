from django.contrib import admin
from .models import Account, Category, Transaction, Budget, RecurringTransaction, SavingsGoal

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
