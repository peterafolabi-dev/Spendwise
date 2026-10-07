from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Q
from django.db.models.signals import post_save
from django.dispatch import receiver

ACCOUNT_TYPES = [
    ('CASH', 'Cash'),
    ('BANK', 'Bank Account'),
    ('CARD', 'Credit Card'),
    ('SAVINGS', 'Savings Account'),
]

TRANSACTION_TYPES = [
    ('INCOME', 'Income'),
    ('EXPENSE', 'Expense'),
]

FREQUENCY_CHOICES = [
    ('WEEKLY', 'Weekly'),
    ('BIWEEKLY', 'Bi-Weekly'),
    ('MONTHLY', 'Monthly'),
    ('YEARLY', 'Yearly'),
]

class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    starting_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    def current_balance(self):
        incomes = self.transactions.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expenses = self.transactions.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return self.starting_balance + incomes - expenses

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon name")

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return f"{self.icon} {self.name}"


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True)
    receipt = models.ImageField(upload_to='receipts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Amount must be greater than zero.'})
        # Buffer: max 7 days in the future
        if self.date > timezone.now().date() + timedelta(days=7):
            raise ValidationError({'date': 'Transaction date cannot be more than 7 days in the future.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_type_display()} of {self.amount} on {self.date}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.OneToOneField(Category, on_delete=models.CASCADE, related_name='budget')
    limit = models.DecimalField(max_digits=12, decimal_places=2)

    def clean(self):
        if self.limit <= Decimal('0.00'):
            raise ValidationError({'limit': 'Budget limit must be greater than zero.'})
        if self.category.type != 'EXPENSE':
            raise ValidationError({'category': 'Budgets can only be set for expense categories.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Budget for {self.category.name}: {self.limit}"


class RecurringTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    next_due_date = models.DateField()
    last_processed = models.DateField(null=True, blank=True)

    def clean(self):
        if self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Amount must be greater than zero.'})

    def __str__(self):
        return f"{self.frequency} {self.get_type_display()} of {self.amount}"


class SavingsGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="The savings account linked to this goal.")
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    target_date = models.DateField()

    def progress_percentage(self):
        balance = self.account.current_balance()
        if balance <= Decimal('0.00'):
            return 0
        if balance >= self.target_amount:
            return 100
        return int((balance / self.target_amount) * 100)

    def __str__(self):
        return self.name


class PasskeyCredential(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    credential_id = models.CharField(max_length=2048, unique=True)
    public_key = models.TextField()
    sign_count = models.IntegerField(default=0)
    device_name = models.CharField(max_length=100, default='Biometric Passkey')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device_name} ({self.user.username})"


def seed_user_defaults(user):
    """Auto-seeds default account and categories for a user."""
    # Seed default account if none exists
    if not Account.objects.filter(user=user).exists():
        Account.objects.create(
            user=user,
            name="Main Checking / Cash Wallet",
            type="BANK",
            starting_balance=Decimal('50000.00')
        )

    # Seed default categories
    default_categories = [
        # Expense
        ("Food & Dining", "EXPENSE", "🍔"),
        ("Groceries", "EXPENSE", "🛒"),
        ("Rent & Housing", "EXPENSE", "🏠"),
        ("Utilities", "EXPENSE", "💡"),
        ("Transportation", "EXPENSE", "🚕"),
        ("Entertainment", "EXPENSE", "🎮"),
        ("Health & Fitness", "EXPENSE", "💪"),
        ("Shopping", "EXPENSE", "🛍️"),
        ("Account Transfer", "EXPENSE", "🔄"),
        # Income
        ("Salary", "INCOME", "💼"),
        ("Freelance", "INCOME", "💻"),
        ("Investments", "INCOME", "📈"),
        ("Gifts", "INCOME", "🎁"),
    ]

    for name, cat_type, icon in default_categories:
        Category.objects.get_or_create(
            user=user,
            name=name,
            defaults={"type": cat_type, "icon": icon}
        )


@receiver(post_save, sender=User)
def create_user_defaults(sender, instance, created, **kwargs):
    if created:
        seed_user_defaults(instance)
