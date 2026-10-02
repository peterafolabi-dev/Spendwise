from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.models import Account, Category, Transaction, Budget, SavingsGoal
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Seeds the database with demo user and realistic data'

    def handle(self, *args, **kwargs):
        # Create Demo User
        if User.objects.filter(username='demo').exists():
            self.stdout.write(self.style.WARNING('Demo user already exists.'))
            user = User.objects.get(username='demo')
            user.delete() # Start fresh
        
        user = User.objects.create_user(username='demo', password='demo12345')
        self.stdout.write(self.style.SUCCESS('Created demo user: demo / demo12345'))

        # Create Accounts
        bank_acc = Account.objects.create(user=user, name='Main Bank Account', type='BANK', starting_balance=Decimal('500000.00'))
        cash_acc = Account.objects.create(user=user, name='Wallet', type='CASH', starting_balance=Decimal('15000.00'))
        savings_acc = Account.objects.create(user=user, name='Emergency Fund', type='SAVINGS', starting_balance=Decimal('200000.00'))
        self.stdout.write(self.style.SUCCESS('Created accounts'))

        # Create Categories
        salary = Category.objects.create(user=user, name='Salary', type='INCOME', icon='💰')
        food = Category.objects.create(user=user, name='Food', type='EXPENSE', icon='🍔')
        transport = Category.objects.create(user=user, name='Transport', type='EXPENSE', icon='🚕')
        rent = Category.objects.create(user=user, name='Rent', type='EXPENSE', icon='🏠')
        entertainment = Category.objects.create(user=user, name='Entertainment', type='EXPENSE', icon='🎮')
        data = Category.objects.create(user=user, name='Data & Airtime', type='EXPENSE', icon='📱')
        self.stdout.write(self.style.SUCCESS('Created categories'))

        # Create Budgets (One over limit)
        Budget.objects.create(user=user, category=food, limit=Decimal('50000.00'))
        Budget.objects.create(user=user, category=transport, limit=Decimal('20000.00'))
        Budget.objects.create(user=user, category=entertainment, limit=Decimal('10000.00')) # Intentionally low to go over
        self.stdout.write(self.style.SUCCESS('Created budgets'))

        # Create Savings Goal
        SavingsGoal.objects.create(user=user, account=savings_acc, name='New Laptop', target_amount=Decimal('800000.00'), target_date=timezone.now().date() + timedelta(days=180))
        self.stdout.write(self.style.SUCCESS('Created savings goal'))

        # Generate 2 months of transactions
        today = timezone.now().date()
        start_date = today - timedelta(days=60)
        
        # Salary every 30 days
        Transaction.objects.create(user=user, account=bank_acc, amount=Decimal('350000.00'), type='INCOME', category=salary, date=start_date + timedelta(days=5), note='Monthly Salary')
        Transaction.objects.create(user=user, account=bank_acc, amount=Decimal('350000.00'), type='INCOME', category=salary, date=start_date + timedelta(days=35), note='Monthly Salary')

        current_date = start_date
        while current_date <= today:
            # Daily food
            Transaction.objects.create(user=user, account=bank_acc, amount=Decimal(random.randint(15, 45) * 100), type='EXPENSE', category=food, date=current_date)
            # Transport every few days
            if random.random() > 0.5:
                Transaction.objects.create(user=user, account=cash_acc, amount=Decimal(random.randint(10, 30) * 100), type='EXPENSE', category=transport, date=current_date)
            # Entertainment (going over budget)
            if random.random() > 0.8:
                Transaction.objects.create(user=user, account=bank_acc, amount=Decimal(random.randint(40, 100) * 100), type='EXPENSE', category=entertainment, date=current_date, note='Weekend vibes')
            
            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS('Generated transactions'))
        self.stdout.write(self.style.SUCCESS('Demo data seeding complete!'))

