from django import forms
from django.contrib.auth.models import User
from .models import Account, Category, Transaction, Budget, RecurringTransaction, SavingsGoal

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'type', 'starting_balance']

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'icon']

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'amount', 'type', 'category', 'date', 'note', 'receipt']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['account'].queryset = Account.objects.filter(user=user)
            self.fields['category'].queryset = Category.objects.filter(user=user)

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'limit']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user, type='EXPENSE')

class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = ['account', 'amount', 'type', 'category', 'note', 'frequency', 'next_due_date']
        widgets = {
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['account'].queryset = Account.objects.filter(user=user)
            self.fields['category'].queryset = Category.objects.filter(user=user)

class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['account', 'name', 'target_amount', 'target_date']
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            savings_accs = Account.objects.filter(user=user, type='SAVINGS')
            if savings_accs.exists():
                self.fields['account'].queryset = savings_accs
            else:
                self.fields['account'].queryset = Account.objects.filter(user=user)
