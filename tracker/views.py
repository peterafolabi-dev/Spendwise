import csv
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.db.models import Sum, F
from django.utils import timezone
from .models import Account, Category, Transaction, Budget, RecurringTransaction, SavingsGoal
from .forms import (AccountForm, CategoryForm, TransactionForm, BudgetForm, 
                   RecurringTransactionForm, SavingsGoalForm)

def rate_limit(key, limit, period):
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, period)
    return True

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

def landing_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')

def signup_view(request):
    ip = get_client_ip(request)
    if not rate_limit(f'signup_{ip}', 5, 3600):
        return HttpResponse('Too many signup attempts', status=429)

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    ip = get_client_ip(request)
    if not rate_limit(f'login_{ip}', 10, 300):
        return HttpResponse('Too many login attempts', status=429)

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    if request.method in ['GET', 'POST']:
        logout(request)
    return redirect('landing')

@login_required
def dashboard_view(request):
    user = request.user
    accounts = Account.objects.filter(user=user)
    total_balance = sum(account.current_balance() for account in accounts) if accounts.exists() else Decimal('0.00')
    
    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    
    # Days left in current month
    import calendar
    _, last_day = calendar.monthrange(today.year, today.month)
    days_left = max(1, last_day - today.day + 1)
    
    transactions = Transaction.objects.filter(user=user, date__gte=current_month_start)
    income = transactions.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses = transactions.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    recent_transactions = Transaction.objects.filter(user=user).order_by('-date', '-created_at')[:8]
    budgets = Budget.objects.filter(user=user).select_related('category')
    
    total_budget_limit = budgets.aggregate(total=Sum('limit'))['total'] or Decimal('0.00')
    budget_remaining = max(Decimal('0.00'), total_budget_limit - expenses)
    safe_to_spend_today = (budget_remaining / Decimal(days_left)) if budget_remaining > 0 else Decimal('0.00')
    
    # Savings goals & Round-ups
    savings_goals = SavingsGoal.objects.filter(user=user)
    primary_goal = savings_goals.first()
    
    # Estimated spare change round-ups (to nearest 100)
    roundup_estimate = Decimal('0.00')
    for tx in transactions.filter(type='EXPENSE'):
        cents = tx.amount % Decimal('100.00')
        if cents > 0:
            roundup_estimate += (Decimal('100.00') - cents)
            
    # Category spending breakdown for SVG Donut
    cat_data = []
    cat_colors = ['#10b981', '#06b6d4', '#f43f5e', '#8b5cf6', '#f59e0b', '#3b82f6', '#ec4899']
    for idx, cat in enumerate(Category.objects.filter(user=user, type='EXPENSE')):
        cat_total = transactions.filter(category=cat).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if cat_total > 0:
            cat_data.append({
                'label': cat.name,
                'value': float(cat_total),
                'icon': cat.icon,
                'color': cat_colors[idx % len(cat_colors)]
            })
            
    # Fallback categories if empty
    if not cat_data:
        cat_data = [
            {'label': 'Groceries', 'value': 28500, 'icon': '🍔', 'color': '#10b981'},
            {'label': 'Transport', 'value': 14200, 'icon': '🚕', 'color': '#06b6d4'},
            {'label': 'Data & Airtime', 'value': 8500, 'icon': '📱', 'color': '#8b5cf6'},
            {'label': 'Entertainment', 'value': 12000, 'icon': '🎮', 'color': '#f59e0b'},
        ]
        
    # 6-Month Trend Data
    months_trend = []
    for i in range(5, -1, -1):
        m_date = (today.replace(day=1) - timezone.timedelta(days=i * 28)).replace(day=1)
        m_end = (m_date + timezone.timedelta(days=32)).replace(day=1)
        m_tx = Transaction.objects.filter(user=user, date__gte=m_date, date__lt=m_end)
        m_inc = m_tx.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        m_exp = m_tx.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        months_trend.append({
            'label': m_date.strftime('%b'),
            'income': float(m_inc),
            'expense': float(m_exp),
        })
        
    # Recurring subscriptions / upcoming
    recurring_bills = RecurringTransaction.objects.filter(user=user).order_by('next_due_date')[:4]
    
    context = {
        'total_balance': total_balance,
        'monthly_income': income,
        'monthly_expenses': expenses,
        'recent_transactions': recent_transactions,
        'budgets': budgets,
        'accounts': accounts,
        'primary_goal': primary_goal,
        'savings_goals': savings_goals,
        'safe_to_spend_today': safe_to_spend_today,
        'budget_remaining': budget_remaining,
        'total_budget_limit': total_budget_limit,
        'days_left': days_left,
        'roundup_estimate': roundup_estimate,
        'cat_data_json': json.dumps(cat_data),
        'months_trend_json': json.dumps(months_trend),
        'recurring_bills': recurring_bills,
    }
    return render(request, 'tracker/dashboard.html', context)

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'tracker/profile.html', {'form': form})

class UserOwnedMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

class UserFormMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

# Account CRUD
class AccountListView(UserOwnedMixin, ListView):
    model = Account
    template_name = 'tracker/accounts.html'

class AccountCreateView(UserOwnedMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('account_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class AccountUpdateView(UserOwnedMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('account_list')

class AccountDeleteView(UserOwnedMixin, DeleteView):
    model = Account
    template_name = 'tracker/generic_confirm_delete.html'
    success_url = reverse_lazy('account_list')

# Category CRUD
class CategoryListView(UserOwnedMixin, ListView):
    model = Category
    template_name = 'tracker/categories.html'

class CategoryCreateView(UserOwnedMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('category_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class CategoryUpdateView(UserOwnedMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('category_list')

@login_required
def category_delete_view(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        uncategorised, created = Category.objects.get_or_create(
            user=request.user, 
            name='Uncategorised',
            defaults={'type': category.type}
        )
        Transaction.objects.filter(category=category).update(category=uncategorised)
        RecurringTransaction.objects.filter(category=category).update(category=uncategorised)
        category.delete()
        return redirect('category_list')
    return render(request, 'tracker/generic_confirm_delete.html', {'object': category})

# Transaction CRUD
class TransactionListView(UserOwnedMixin, ListView):
    model = Transaction
    template_name = 'tracker/transactions.html'
    ordering = ['-date', '-created_at']

class TransactionCreateView(UserOwnedMixin, UserFormMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('transaction_list')

class TransactionUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('transaction_list')

class TransactionDeleteView(UserOwnedMixin, DeleteView):
    model = Transaction
    template_name = 'tracker/generic_confirm_delete.html'
    success_url = reverse_lazy('transaction_list')

@login_required
def quick_add_transaction(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            account = get_object_or_404(Account, pk=data['account_id'], user=request.user)
            category = get_object_or_404(Category, pk=data.get('category_id'), user=request.user) if data.get('category_id') else None
            t = Transaction.objects.create(
                user=request.user,
                account=account,
                amount=Decimal(data['amount']),
                type=data['type'],
                category=category,
                note=data.get('note', '')
            )
            return JsonResponse({'status': 'success', 'id': t.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

# Budget CRUD
class BudgetListView(UserOwnedMixin, ListView):
    model = Budget
    template_name = 'tracker/budgets.html'

class BudgetCreateView(UserOwnedMixin, UserFormMixin, CreateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('budget_list')

class BudgetUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('budget_list')

class BudgetDeleteView(UserOwnedMixin, DeleteView):
    model = Budget
    template_name = 'tracker/generic_confirm_delete.html'
    success_url = reverse_lazy('budget_list')

# SavingsGoal CRUD
class SavingsGoalListView(UserOwnedMixin, ListView):
    model = SavingsGoal
    template_name = 'tracker/savings_goals.html'

class SavingsGoalCreateView(UserOwnedMixin, UserFormMixin, CreateView):
    model = SavingsGoal
    form_class = SavingsGoalForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('savings_list')

class SavingsGoalUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = SavingsGoal
    form_class = SavingsGoalForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('savings_list')

class SavingsGoalDeleteView(UserOwnedMixin, DeleteView):
    model = SavingsGoal
    template_name = 'tracker/generic_confirm_delete.html'
    success_url = reverse_lazy('savings_list')

# RecurringTransaction CRUD
class RecurringListView(UserOwnedMixin, ListView):
    model = RecurringTransaction
    template_name = 'tracker/recurringtransactions.html'

class RecurringCreateView(UserOwnedMixin, UserFormMixin, CreateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('recurring_list')

class RecurringUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'tracker/generic_form.html'
    success_url = reverse_lazy('recurring_list')

class RecurringDeleteView(UserOwnedMixin, DeleteView):
    model = RecurringTransaction
    template_name = 'tracker/generic_confirm_delete.html'
    success_url = reverse_lazy('recurring_list')

# Reports
@login_required
def reports_view(request):
    transactions = Transaction.objects.filter(user=request.user)
    expenses = transactions.filter(type='EXPENSE').values('category__name').annotate(total=Sum('amount'))
    incomes = transactions.filter(type='INCOME').values('category__name').annotate(total=Sum('amount'))
    return render(request, 'tracker/reports.html', {
        'expenses': list(expenses),
        'incomes': list(incomes)
    })

# Export / Import
def escape_csv_formula(value):
    if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@'):
        return "'" + value
    return value

@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Account', 'Type', 'Category', 'Amount', 'Note'])
    
    transactions = Transaction.objects.filter(user=request.user).order_by('-date')
    for t in transactions:
        writer.writerow([
            t.date,
            t.account.name,
            t.type,
            t.category.name if t.category else 'None',
            t.amount,
            escape_csv_formula(t.note)
        ])
    return response

@login_required
def import_csv(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            return HttpResponse('Not a CSV file', status=400)
        
        data = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(data)
        
        # Skip header if exists
        header = next(reader, None)
        
        for row in reader:
            try:
                date_str, acc_name, type_val, cat_name, amount, note = row
                
                account, _ = Account.objects.get_or_create(user=request.user, name=acc_name, defaults={'type': 'CASH'})
                category = None
                if cat_name and cat_name != 'None':
                    category, _ = Category.objects.get_or_create(user=request.user, name=cat_name, defaults={'type': type_val})
                
                t = Transaction(
                    user=request.user,
                    account=account,
                    type=type_val,
                    category=category,
                    amount=Decimal(amount),
                    date=date_str,
                    note=note
                )
                t.clean() # validate
                t.save()
            except Exception as e:
                # Skip bad rows
                continue
        return redirect('transaction_list')
    return render(request, 'tracker/import_csv.html')

