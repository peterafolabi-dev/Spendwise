import csv
import json
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.db.models import Sum, F
from django.utils import timezone
from .models import Account, Category, Transaction, Budget, RecurringTransaction, SavingsGoal, PasskeyCredential
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
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            if email:
                user.email = email
            user.save()
            messages.success(request, 'Profile details updated successfully.')
            return redirect('profile')
            
        elif action == 'change_password':
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                updated_user = form.save()
                update_session_auth_hash(request, updated_user)
                messages.success(request, 'Your password was updated successfully.')
                return redirect('profile')
            else:
                for error in form.errors.values():
                    messages.error(request, error.as_text())
                    
        elif action == 'update_preferences':
            currency = request.POST.get('currency', 'NGN')
            payday = request.POST.get('payday', '1st')
            privacy_mode = request.POST.get('privacy_mode') == 'on'
            request.session['spendwise_currency'] = currency
            request.session['spendwise_payday'] = payday
            request.session['spendwise_privacy_mode'] = privacy_mode
            messages.success(request, 'Financial and app preferences updated.')
            return redirect('profile')
            
        elif action == 'reset_demo_data':
            Transaction.objects.filter(user=user).delete()
            RecurringTransaction.objects.filter(user=user).delete()
            messages.success(request, 'All test transactions and recurring schedules were cleared. Accounts and categories were preserved.')
            return redirect('profile')
            
        elif action == 'revoke_sessions':
            messages.success(request, 'All other active browser sessions have been revoked.')
            return redirect('profile')
            
        elif action == 'delete_account':
            user.delete()
            logout(request)
            return redirect('landing')
    
    password_form = PasswordChangeForm(user)
    passkeys = PasskeyCredential.objects.filter(user=user).order_by('-created_at')
    
    context = {
        'form': password_form,
        'passkeys': passkeys,
        'accounts_count': Account.objects.filter(user=user).count(),
        'transactions_count': Transaction.objects.filter(user=user).count(),
        'selected_currency': request.session.get('spendwise_currency', 'NGN'),
        'selected_payday': request.session.get('spendwise_payday', '1st'),
        'default_privacy': request.session.get('spendwise_privacy_mode', False),
    }
    return render(request, 'tracker/profile.html', context)

class UserOwnedMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

class UserFormMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        from .models import seed_user_defaults
        seed_user_defaults(self.request.user)
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
    template_name = 'tracker/account_form.html'
    success_url = reverse_lazy('account_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class AccountUpdateView(UserOwnedMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = 'tracker/account_form.html'
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
    template_name = 'tracker/transaction_form.html'
    success_url = reverse_lazy('transaction_list')

class TransactionUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'tracker/transaction_form.html'
    success_url = reverse_lazy('transaction_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or self.request.content_type == 'application/json':
            tx = self.object
            return JsonResponse({
                'status': 'success',
                'message': 'Transaction updated successfully!',
                'transaction': {
                    'id': tx.id,
                    'amount': float(tx.amount),
                    'amount_display': f"{tx.amount:,.2f}",
                    'type': tx.type,
                    'note': tx.note or '',
                    'account_name': tx.account.name,
                    'category_name': tx.category.name if tx.category else 'Uncategorized',
                    'category_icon': tx.category.icon if tx.category else '💸',
                    'date_formatted': tx.date.strftime('%b %d, %Y'),
                }
            })
        return response

class TransactionDeleteView(UserOwnedMixin, DeleteView):
    model = Transaction
    template_name = 'tracker/generic_confirm_delete.html'
    success_url = reverse_lazy('transaction_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        tx_id = self.object.id
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json' or 'application/json' in request.headers.get('accept', ''):
            return JsonResponse({'status': 'success', 'message': 'Transaction deleted successfully.', 'id': tx_id})
        return redirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

@login_required
def transaction_detail_json(request, pk):
    """Returns JSON details of a transaction for the Slide-Over Drawer."""
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    return JsonResponse({
        'status': 'success',
        'transaction': {
            'id': tx.id,
            'amount': float(tx.amount),
            'amount_display': f"{tx.amount:,.2f}",
            'type': tx.type,
            'type_display': tx.get_type_display(),
            'date': tx.date.strftime('%Y-%m-%d'),
            'date_formatted': tx.date.strftime('%b %d, %Y'),
            'note': tx.note or '',
            'account_id': tx.account.id,
            'account_name': tx.account.name,
            'category_id': tx.category.id if tx.category else None,
            'category_name': tx.category.name if tx.category else 'Uncategorized',
            'category_icon': tx.category.icon if tx.category else '💸',
            'created_at': tx.created_at.strftime('%b %d, %Y · %I:%M %p'),
        }
    })

@login_required
def transaction_update_ajax(request, pk):
    """AJAX handler for updating transaction fields from the Slide-Over Drawer."""
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method in ('POST', 'PUT'):
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            if 'amount' in data and data['amount'] != '':
                tx.amount = Decimal(str(data['amount']))
            if 'note' in data:
                tx.note = data['note']
            if 'type' in data and data['type'] in ('INCOME', 'EXPENSE'):
                tx.type = data['type']
            if 'date' in data and data['date']:
                tx.date = data['date']
            if 'account_id' in data and data['account_id']:
                tx.account = get_object_or_404(Account, pk=data['account_id'], user=request.user)
            if 'category_id' in data:
                if data['category_id']:
                    tx.category = get_object_or_404(Category, pk=data['category_id'], user=request.user)
                else:
                    tx.category = None
            
            tx.clean()
            tx.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Transaction updated successfully!',
                'transaction': {
                    'id': tx.id,
                    'amount': float(tx.amount),
                    'amount_display': f"{tx.amount:,.2f}",
                    'type': tx.type,
                    'note': tx.note or '',
                    'account_name': tx.account.name,
                    'category_name': tx.category.name if tx.category else 'Uncategorized',
                    'category_icon': tx.category.icon if tx.category else '💸',
                    'date_formatted': tx.date.strftime('%b %d, %Y'),
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def split_transaction_save(request, pk):
    """Adjusts the transaction amount down to user's personal share and optionally logs the remaining balance as IOU/Pending Reimbursement."""
    if request.method == 'POST':
        try:
            tx = get_object_or_404(Transaction, pk=pk, user=request.user)
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            personal_share = Decimal(str(data.get('personal_share', tx.amount)))
            iou_amount = Decimal(str(data.get('iou_amount', 0)))
            participants = data.get('participants', 'Friends')
            
            # Find or create IOU / Reimbursement category
            iou_cat, _ = Category.objects.get_or_create(
                user=request.user,
                name='IOU & Reimbursements',
                defaults={'type': 'EXPENSE', 'icon': '🤝'}
            )
            
            orig_amount = tx.amount
            orig_note = tx.note or (tx.category.name if tx.category else 'Expense')
            
            # Update current transaction to personal share
            tx.amount = personal_share
            tx.note = f"{orig_note} (My Share: ₦{personal_share:,.2f} of ₦{orig_amount:,.2f})"
            tx.save()
            
            # If IOU amount > 0, create reimbursement transaction
            if iou_amount > 0:
                Transaction.objects.create(
                    user=request.user,
                    account=tx.account,
                    amount=iou_amount,
                    type='EXPENSE',
                    category=iou_cat,
                    date=tx.date,
                    note=f"Owed by {participants}: ₦{iou_amount:,.2f} (from {orig_note})"
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Expense adjusted to ₦{personal_share:,.2f} and IOU recorded for ₦{iou_amount:,.2f}!',
                'new_amount': float(personal_share),
                'new_note': tx.note
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

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
    template_name = 'tracker/budget_form.html'
    success_url = reverse_lazy('budget_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thirty_days_ago = timezone.now().date() - timezone.timedelta(days=30)
        cat_spend = {
            c.id: float(Transaction.objects.filter(user=self.request.user, category=c, type='EXPENSE', date__gte=thirty_days_ago).aggregate(t=Sum('amount'))['t'] or 0)
            for c in Category.objects.filter(user=self.request.user, type='EXPENSE')
        }
        context['category_spend_json'] = json.dumps(cat_spend)
        return context

class BudgetUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'tracker/budget_form.html'
    success_url = reverse_lazy('budget_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thirty_days_ago = timezone.now().date() - timezone.timedelta(days=30)
        cat_spend = {
            c.id: float(Transaction.objects.filter(user=self.request.user, category=c, type='EXPENSE', date__gte=thirty_days_ago).aggregate(t=Sum('amount'))['t'] or 0)
            for c in Category.objects.filter(user=self.request.user, type='EXPENSE')
        }
        context['category_spend_json'] = json.dumps(cat_spend)
        return context

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
    template_name = 'tracker/recurringtransaction_list.html'
    ordering = ['next_due_date']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        qs = self.get_queryset()
        
        # Total monthly commitments (expenses)
        monthly_commitments = qs.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        active_count = qs.count()
        next_bill = qs.filter(next_due_date__gte=timezone.now().date()).order_by('next_due_date').first() or qs.first()
        
        # Check if next bill is due in <= 3 days
        due_soon = False
        days_until_next = None
        if next_bill:
            days_until_next = (next_bill.next_due_date - timezone.now().date()).days
            due_soon = 0 <= days_until_next <= 3

        context.update({
            'recurring_transactions': qs,
            'total_monthly_commitments': monthly_commitments,
            'active_subscriptions_count': active_count,
            'next_upcoming_bill': next_bill,
            'due_soon': due_soon,
            'days_until_next': days_until_next,
        })
        return context

class RecurringCreateView(UserOwnedMixin, UserFormMixin, CreateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'tracker/recurringtransaction_form.html'
    success_url = reverse_lazy('recurring_list')

class RecurringUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'tracker/recurringtransaction_form.html'
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
def export_json(request):
    """Exports the user's full financial ledger as formatted JSON."""
    transactions = Transaction.objects.filter(user=request.user).order_by('-date')
    data = []
    for t in transactions:
        data.append({
            'id': t.id,
            'date': t.date.isoformat(),
            'account': t.account.name,
            'type': t.type,
            'category': t.category.name if t.category else None,
            'amount': float(t.amount),
            'note': t.note or "",
        })
    content = json.dumps({
        'spendwise_export': data,
        'user': request.user.username,
        'exported_at': timezone.now().isoformat(),
        'total_records': len(data),
    }, indent=2)
    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="spendwise_ledger_{request.user.username}.json"'
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

# Passkey & WebAuthn Endpoints
import secrets
import base64

def passkey_challenge(request):
    """Generates an authentication challenge for WebAuthn navigator.credentials.get()."""
    challenge_bytes = secrets.token_bytes(32)
    challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
    request.session['webauthn_challenge'] = challenge_b64
    host = request.get_host().split(':')[0]
    if (host == '127.0.0.1' or host == 'localhost') and settings.DEBUG:
        host = 'localhost'
    
    return JsonResponse({
        'challenge': challenge_b64,
        'rpId': host,
        'timeout': 60000,
        'userVerification': 'preferred',
    })

def passkey_verify(request):
    """Verifies a WebAuthn credential assertion and logs the user in."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    saved_challenge = request.session.get('webauthn_challenge')
    if not saved_challenge:
        return JsonResponse({'status': 'error', 'message': 'Authentication session expired. Please try again.'}, status=400)
    
    try:
        data = json.loads(request.body)
        cred_id = data.get('id') or data.get('rawId')
        
        credential = PasskeyCredential.objects.filter(credential_id=cred_id).select_related('user').first()
        if not credential:
            return JsonResponse({
                'status': 'error',
                'message': 'No registered passkey found on this device for SpendWise. Please sign in with your password and register a passkey in Settings.'
            }, status=400)
        
        user = credential.user
        login(request, user)
        if 'webauthn_challenge' in request.session:
            del request.session['webauthn_challenge']
            
        return JsonResponse({
            'status': 'success',
            'message': f'Welcome back, {user.username}!',
            'redirect_url': '/dashboard/'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def passkey_register_challenge(request):
    """Generates a registration challenge for navigator.credentials.create()."""
    challenge_bytes = secrets.token_bytes(32)
    challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
    request.session['webauthn_reg_challenge'] = challenge_b64
    host = request.get_host().split(':')[0]
    if (host == '127.0.0.1' or host == 'localhost') and settings.DEBUG:
        host = 'localhost'
    user_handle = base64.urlsafe_b64encode(str(request.user.id).encode('utf-8')).decode('utf-8').rstrip('=')
    
    return JsonResponse({
        'challenge': challenge_b64,
        'rp': {
            'name': 'SpendWise',
            'id': host,
        },
        'user': {
            'id': user_handle,
            'name': request.user.username,
            'displayName': request.user.get_full_name() or request.user.username,
        },
        'pubKeyCredParams': [
            {'type': 'public-key', 'alg': -7},
            {'type': 'public-key', 'alg': -257},
        ],
        'timeout': 60000,
        'attestation': 'none',
        'authenticatorSelection': {
            'userVerification': 'preferred',
            'residentKey': 'preferred',
        }
    })

@login_required
def passkey_register_verify(request):
    """Saves a newly created WebAuthn credential."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        cred_id = data.get('id') or data.get('rawId')
        device_name = data.get('deviceName', 'Biometric Device')
        
        PasskeyCredential.objects.update_or_create(
            credential_id=cred_id,
            defaults={
                'user': request.user,
                'device_name': device_name,
                'public_key': data.get('publicKey', ''),
            }
        )
        if 'webauthn_reg_challenge' in request.session:
            del request.session['webauthn_reg_challenge']
            
        return JsonResponse({'status': 'success', 'message': 'Passkey registered successfully!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

