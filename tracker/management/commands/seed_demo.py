from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.models import Account, Category, Transaction, Budget, SavingsGoal
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Seeds the database with a demo user and demo data'

    def handle(self, *args, **kwargs):
        # Create user
        user, created = User.objects.get_or_create(username='demo')
        if created:
            user.set_password('demo12345')
            user.save()
            self.stdout.write('Created demo user.')
        else:
            self.stdout.write('Demo user already exists. Overwriting data.')
            user.accounts.all().delete()
            user.categories.all().delete()

        # Accounts
        cash = Account.objects.create(user=user, name='Wallet', type='CASH', starting_balance=Decimal('200.00'))
        bank = Account.objects.create(user=user, name='Main Bank', type='BANK', starting_balance=Decimal('1500.00'))
        savings = Account.objects.create(user=user, name='Emergency Fund', type='SAVINGS', starting_balance=Decimal('5000.00'))

        # Categories
        cat_food = Category.objects.create(user=user, name='Food & Dining', type='EXPENSE', icon='🍔')
        cat_rent = Category.objects.create(user=user, name='Rent', type='EXPENSE', icon='🏠')
        cat_salary = Category.objects.create(user=user, name='Salary', type='INCOME', icon='💼')
        cat_fun = Category.objects.create(user=user, name='Entertainment', type='EXPENSE', icon='🎉')

        # Budgets
        Budget.objects.create(user=user, category=cat_food, limit=Decimal('400.00'))
        # Budget over limit
        Budget.objects.create(user=user, category=cat_fun, limit=Decimal('50.00'))

        # Savings Goal
        SavingsGoal.objects.create(user=user, account=savings, name='Vacation', target_amount=Decimal('8000.00'), target_date=timezone.now().date() + timedelta(days=180))

        # Transactions (2 months of data)
        today = timezone.now().date()
        for i in range(60):
            d = today - timedelta(days=i)
            # Add some expenses
            Transaction.objects.create(user=user, account=bank, amount=Decimal(random.randint(10, 30)), type='EXPENSE', category=cat_food, date=d)
            if i % 30 == 0:
                # Add rent
                Transaction.objects.create(user=user, account=bank, amount=Decimal('1000.00'), type='EXPENSE', category=cat_rent, date=d)
                # Add salary
                Transaction.objects.create(user=user, account=bank, amount=Decimal('3000.00'), type='INCOME', category=cat_salary, date=d)

        # Force fun budget over limit
        Transaction.objects.create(user=user, account=bank, amount=Decimal('100.00'), type='EXPENSE', category=cat_fun, date=today)

        self.stdout.write(self.style.SUCCESS('Successfully seeded demo data'))
