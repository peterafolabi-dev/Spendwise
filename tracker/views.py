import csv
import json
import base64
import logging
import re
import secrets
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, F
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Account, Category, Transaction, Budget, RecurringTransaction, SavingsGoal, PasskeyCredential
from .forms import (AccountForm, CategoryForm, TransactionForm, BudgetForm, 
                   RecurringTransactionForm, SavingsGoalForm)
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from webauthn.helpers.exceptions import WebAuthnException

logger = logging.getLogger(__name__)

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
    today = timezone.now().date()
    current_month_start = today.replace(day=1)

    account_balances = accounts.annotate(
        income=Sum('transactions__amount', filter=Q(transactions__type='INCOME')),
        expenses=Sum('transactions__amount', filter=Q(transactions__type='EXPENSE')),
    )
    total_balance = sum(
        (
            account.starting_balance
            + (account.income or Decimal('0.00'))
            - (account.expenses or Decimal('0.00'))
            for account in account_balances
        ),
        Decimal('0.00'),
    )

    import calendar
    _, last_day = calendar.monthrange(today.year, today.month)
    days_left = max(1, last_day - today.day + 1)

    transactions = Transaction.objects.filter(user=user, date__gte=current_month_start)
    income = transactions.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses = transactions.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    recent_transactions = Transaction.objects.filter(user=user).order_by('-date', '-created_at')[:8]
    budgets = Budget.objects.filter(user=user).select_related('category').annotate(
        month_spent=Sum(
            'category__transactions__amount',
            filter=Q(
                category__transactions__user=user,
                category__transactions__type='EXPENSE',
                category__transactions__date__gte=current_month_start,
                category__transactions__date__lte=today,
            ),
        )
    )

    total_budget_limit = Budget.objects.filter(user=user).aggregate(total=Sum('limit'))['total'] or Decimal('0.00')
    budget_remaining = sum(
        (
            max(Decimal('0.00'), budget.limit - (budget.month_spent or Decimal('0.00')))
            for budget in budgets
        ),
        Decimal('0.00'),
    )
    recurring_due = RecurringTransaction.objects.filter(
        user=user,
        type='EXPENSE',
        next_due_date__gte=today,
        next_due_date__lte=today.replace(day=last_day),
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    budget_remaining = max(Decimal('0.00'), budget_remaining - recurring_due)
    safe_to_spend_today = budget_remaining / Decimal(days_left)

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
    monthly_categories = Category.objects.filter(
        user=user,
        type='EXPENSE',
    ).annotate(
        total=Sum(
            'transactions__amount',
            filter=Q(
                transactions__user=user,
                transactions__type='EXPENSE',
                transactions__date__gte=current_month_start,
                transactions__date__lte=today,
            ),
        )
    ).filter(total__gt=0).order_by('-total')
    for idx, category in enumerate(monthly_categories):
        cat_data.append({
            'label': category.name,
            'value': float(category.total),
            'icon': category.icon,
            'color': cat_colors[idx % len(cat_colors)],
        })

    months_trend = []
    first_month = current_month_start
    month_starts = [first_month]
    for _ in range(5):
        previous_month = month_starts[0] - timezone.timedelta(days=1)
        month_starts.insert(0, previous_month.replace(day=1))
    for m_date in month_starts:
        m_end = (m_date.replace(day=28) + timezone.timedelta(days=4)).replace(day=1)
        m_tx = Transaction.objects.filter(user=user, date__gte=m_date, date__lt=m_end)
        m_inc = m_tx.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        m_exp = m_tx.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        months_trend.append({
            'label': m_date.strftime('%b'),
            'income': float(m_inc),
            'expense': float(m_exp),
        })

    history_start = today - timezone.timedelta(days=89)
    history = Transaction.objects.filter(
        user=user,
        date__gte=history_start,
        date__lte=today,
    ).aggregate(
        income=Sum('amount', filter=Q(type='INCOME')),
        expenses=Sum('amount', filter=Q(type='EXPENSE')),
    )
    historical_income = history['income'] or Decimal('0.00')
    historical_expenses = history['expenses'] or Decimal('0.00')
    average_daily_net = (historical_income - historical_expenses) / Decimal('90')
    forecast = [
        {
            'days': days,
            'balance': float(total_balance + average_daily_net * Decimal(days)),
        }
        for days in (0, 30, 60, 90)
    ] if historical_income or historical_expenses else []
    projected_balance = total_balance + average_daily_net * Decimal('90') if forecast else None

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
        'budget_remaining_ratio': (
            min(100, int(budget_remaining / total_budget_limit * 100))
            if total_budget_limit > 0 else 0
        ),
        'budget_gauge_offset': (
            119.38 * (1 - min(100, int(budget_remaining / total_budget_limit * 100)) / 100)
            if total_budget_limit > 0 else 119.38
        ),
        'days_left': days_left,
        'roundup_estimate': roundup_estimate,
        'cat_data_json': json.dumps(cat_data),
        'months_trend_json': json.dumps(months_trend),
        'forecast_json': json.dumps(forecast),
        'projected_balance': projected_balance,
        'forecast_has_data': bool(forecast),
        'recurring_bills': recurring_bills,
    }
    return render(request, 'tracker/dashboard.html', context)


def _copilot_metrics(user):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    account_balances = Account.objects.filter(user=user).annotate(
        income=Sum('transactions__amount', filter=Q(transactions__type='INCOME')),
        expenses=Sum('transactions__amount', filter=Q(transactions__type='EXPENSE')),
    )
    balance = sum(
        (
            account.starting_balance
            + (account.income or Decimal('0.00'))
            - (account.expenses or Decimal('0.00'))
            for account in account_balances
        ),
        Decimal('0.00'),
    )
    transactions = Transaction.objects.filter(
        user=user,
        date__gte=month_start,
        date__lte=today,
    )
    month_expenses = transactions.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    top_category = Category.objects.filter(
        user=user,
        type='EXPENSE',
    ).annotate(
        spent=Sum(
            'transactions__amount',
            filter=Q(
                transactions__user=user,
                transactions__type='EXPENSE',
                transactions__date__gte=month_start,
                transactions__date__lte=today,
            ),
        )
    ).filter(spent__gt=0).order_by('-spent').first()
    budget_total = Decimal('0.00')
    budgets = Budget.objects.filter(user=user).select_related('category').annotate(
        spent=Sum(
            'category__transactions__amount',
            filter=Q(
                category__transactions__user=user,
                category__transactions__type='EXPENSE',
                category__transactions__date__gte=month_start,
                category__transactions__date__lte=today,
            ),
        )
    )
    for budget in budgets:
        budget_total += max(
            Decimal('0.00'),
            budget.limit - (budget.spent or Decimal('0.00')),
        )
    return {
        'today': today,
        'balance': balance,
        'month_expenses': month_expenses,
        'top_category': top_category,
        'budget_remaining': budget_total,
    }


@login_required
@ensure_csrf_cookie
def copilot_context(request):
    metrics = _copilot_metrics(request.user)
    greeting = (
        f"Hi {request.user.first_name or request.user.username}! Here is your recorded snapshot:\n"
        f"💰 Account balance: ₦{metrics['balance']:,.2f}\n"
        f"📊 Spending this month: ₦{metrics['month_expenses']:,.2f}"
    )
    if metrics['top_category']:
        category = metrics['top_category']
        greeting += f"\n🛒 Top category: {category.name} at ₦{category.spent:,.2f}"
    else:
        greeting += "\n🛒 No categorized expenses recorded this month yet."
    return JsonResponse({'greeting': greeting})


@login_required
def copilot_chat(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Send a valid JSON question.'}, status=400)
    if not isinstance(data, dict) or not isinstance(data.get('message'), str):
        return JsonResponse({'status': 'error', 'message': 'Enter a question to continue.'}, status=400)
    question = data['message'].strip()[:500]
    if not question:
        return JsonResponse({'status': 'error', 'message': 'Enter a question to continue.'}, status=400)

    metrics = _copilot_metrics(request.user)
    lowered = question.casefold()
    if any(term in lowered for term in ('safe to spend', 'daily limit', 'daily budget', 'today')):
        reply = (
            f"📅 YOUR CURRENT BUDGET\n"
            f"About ₦{metrics['budget_remaining']:,.2f} remains across your monthly category budgets after recorded spending.\n"
            "Upcoming recurring bills are not included in this chat estimate. Check the dashboard before making a spending decision."
        )
    elif any(term in lowered for term in ('grocer', 'food', 'category', 'top spend')):
        category = metrics['top_category']
        if category:
            reply = (
                f"📊 THIS MONTH'S TOP SPENDING\n"
                f"{category.name}: ₦{category.spent:,.2f}\n"
                f"All recorded expenses this month: ₦{metrics['month_expenses']:,.2f}."
            )
        else:
            reply = "📊 No categorized expenses are recorded for this month yet. Add transactions with categories to see a useful breakdown."
    elif 'balance' in lowered or 'net worth' in lowered or 'runway' in lowered:
        reply = (
            f"💰 RECORDED ACCOUNT BALANCE\n"
            f"Your accounts currently total ₦{metrics['balance']:,.2f}, based on their starting balances and recorded transactions.\n"
            "This is not a full net-worth calculation; debts and assets outside SpendWise are not included."
        )
    elif 'save' in lowered or 'saving' in lowered:
        amount_match = re.search(r'(?:₦|ngn)?\s*(\d[\d,]*(?:\.\d{1,2})?)', lowered)
        months_match = re.search(r'(\d+)\s*(?:months?|mos?|mo)\b', lowered)
        if amount_match and months_match:
            monthly_amount = Decimal(amount_match.group(1).replace(',', ''))
            months = int(months_match.group(1))
            if monthly_amount > 0 and 1 <= months <= 600:
                reply = (
                    f"🎯 SAVINGS SCENARIO\n"
                    f"Saving ₦{monthly_amount:,.2f} each month for {months} months adds "
                    f"₦{monthly_amount * months:,.2f}, before interest or fees.\n"
                    "Set a target in Savings Goals and compare the contribution with your actual budget."
                )
            else:
                reply = "Enter a positive monthly amount and a timeframe of 1–600 months for a simple savings estimate."
        else:
            reply = (
                f"🎯 SAVINGS NEXT STEP\n"
                f"Your recorded monthly budget balance is ₦{metrics['budget_remaining']:,.2f} before upcoming bills.\n"
                "Choose a monthly contribution that leaves room for essentials, then track it as a savings goal."
            )
    elif any(term in lowered for term in ('tip', 'advice', 'budget', 'help')):
        reply = (
            f"💡 A PRACTICAL NEXT STEP\n"
            f"You have recorded ₦{metrics['month_expenses']:,.2f} in expenses this month"
            + (
                f", with {metrics['top_category'].name} currently highest at ₦{metrics['top_category'].spent:,.2f}."
                if metrics['top_category'] else "."
            )
            + "\nReview that category's budget and upcoming commitments before changing your spending plan."
        )
    else:
        reply = (
            "I can help explain your recorded account balance, this month's top spending, budget remainder, "
            "or a simple savings scenario. I use rules and your recorded totals—not a generative AI model—and "
            "this is educational guidance, not financial advice."
        )

    return JsonResponse({'status': 'success', 'reply': reply})

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
            payday = request.POST.get('payday', '1st')
            privacy_mode = request.POST.get('privacy_mode') == 'on'
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

class AccountListView(UserOwnedMixin, ListView):
    model = Account
    template_name = 'tracker/accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        accounts = list(self.get_queryset())
        total_balance = sum((acc.current_balance() for acc in accounts), Decimal('0.00'))
        total_inflow = Transaction.objects.filter(user=user, type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        total_outflow = Transaction.objects.filter(user=user, type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        context.update({
            'total_balance': total_balance,
            'accounts_count': len(accounts),
            'total_inflow': total_inflow,
            'total_outflow': total_outflow,
        })
        return context

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

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('q', '').strip()[:100]
        flow_type = self.request.GET.get('type', '')
        account_id = self.request.GET.get('account')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')

        if search:
            search_filter = (
                Q(note__icontains=search)
                | Q(category__name__icontains=search)
                | Q(account__name__icontains=search)
            )
            try:
                search_amount = Decimal(search.replace(',', ''))
                if search_amount.is_finite():
                    search_filter |= Q(amount=search_amount)
            except (InvalidOperation, ValueError):
                pass
            qs = qs.filter(search_filter)
        if flow_type in {'INCOME', 'EXPENSE'}:
            qs = qs.filter(type=flow_type)
        if account_id and not account_id.isdecimal():
            return qs.none()
        if account_id:
            qs = qs.filter(account_id=account_id)
        if date_from:
            parsed_date = parse_date(date_from)
            if not parsed_date:
                return qs.none()
            qs = qs.filter(date__gte=parsed_date)
        if date_to:
            parsed_date = parse_date(date_to)
            if not parsed_date:
                return qs.none()
            qs = qs.filter(date__lte=parsed_date)
        if date_from and date_to and date_from > date_to:
            return qs.none()
        return qs

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

    def get_queryset(self):
        budgets = list(super().get_queryset().select_related('category'))
        today = timezone.localdate()
        month_start = today.replace(day=1)
        next_month = (month_start + timezone.timedelta(days=32)).replace(day=1)
        spent_by_category = dict(
            Transaction.objects.filter(
                user=self.request.user,
                type='EXPENSE',
                date__gte=month_start,
                date__lt=next_month,
                category_id__in=[budget.category_id for budget in budgets],
            )
            .values('category_id')
            .annotate(total=Sum('amount'))
            .values_list('category_id', 'total')
        )

        for budget in budgets:
            spent = spent_by_category.get(budget.category_id, Decimal('0.00'))
            budget.spent = spent
            budget.usage_percent = min(int(spent * 100 / budget.limit), 100)
            budget.is_over_limit = spent > budget.limit
            budget.overage = max(spent - budget.limit, Decimal('0.00'))
            budget.is_near_limit = not budget.is_over_limit and spent >= budget.limit * Decimal('0.8')

        return budgets

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
    template_name = 'tracker/savings_form.html'
    success_url = reverse_lazy('savings_list')

class SavingsGoalUpdateView(UserOwnedMixin, UserFormMixin, UpdateView):
    model = SavingsGoal
    form_class = SavingsGoalForm
    template_name = 'tracker/savings_form.html'
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
        
        monthly_commitments = Decimal('0.00')
        monthly_factors = {
            'WEEKLY': Decimal(52) / Decimal(12),
            'BIWEEKLY': Decimal(26) / Decimal(12),
            'MONTHLY': Decimal(1),
            'YEARLY': Decimal(1) / Decimal(12),
        }
        for recurring in qs.filter(type='EXPENSE'):
            monthly_commitments += recurring.amount * monthly_factors[recurring.frequency]
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

def _webauthn_rp_and_origin(request):
    origin = (
        getattr(settings, 'WEBAUTHN_ORIGIN', '')
        or request.build_absolute_uri('/')
    ).rstrip('/')
    rp_id = (getattr(settings, 'WEBAUTHN_RP_ID', '') or urlsplit(origin).hostname or '').lower().strip('.')
    if not rp_id:
        raise ValueError('Could not determine the WebAuthn relying-party domain.')
    if rp_id == '127.0.0.1':
        rp_id = 'localhost'
    return rp_id, origin


def _new_webauthn_challenge(request, name, rp_id, origin):
    challenge = secrets.token_bytes(32)
    request.session[name] = {
        'challenge': base64.urlsafe_b64encode(challenge).decode('ascii').rstrip('='),
        'rp_id': rp_id,
        'origin': origin,
        'expires_at': int(time.time()) + 300,
    }
    return challenge


def _take_webauthn_challenge(request, name):
    state = request.session.pop(name, None)
    if not isinstance(state, dict) or state.get('expires_at', 0) < time.time():
        return None
    try:
        state['challenge_bytes'] = base64url_to_bytes(state['challenge'])
    except (KeyError, ValueError):
        return None
    return state


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def passkey_challenge(request):
    """Create a single-use WebAuthn assertion challenge."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    ip = get_client_ip(request) or 'unknown'
    if not rate_limit(f'passkey_login_{ip}', 10, 300):
        return JsonResponse({'status': 'error', 'message': 'Too many passkey attempts. Please wait and try again.'}, status=429)

    rp_id, origin = _webauthn_rp_and_origin(request)
    challenge = _new_webauthn_challenge(request, 'webauthn_challenge', rp_id, origin)
    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        timeout=60000,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return JsonResponse(json.loads(options_to_json(options)))


def passkey_verify(request):
    """Verify a WebAuthn assertion before creating an authenticated session."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    challenge = _take_webauthn_challenge(request, 'webauthn_challenge')
    if not challenge:
        return JsonResponse(
            {'status': 'error', 'message': 'Authentication challenge expired. Please try again.'},
            status=400,
        )

    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return JsonResponse({'status': 'error', 'message': 'Invalid passkey response.'}, status=400)
        credential_id = data.get('id')
        if (
            not isinstance(credential_id, str)
            or not credential_id
            or data.get('rawId') != credential_id
        ):
            return JsonResponse({'status': 'error', 'message': 'Invalid passkey response.'}, status=400)
        credential = (
            PasskeyCredential.objects.select_related('user')
            .filter(credential_id=credential_id)
            .first()
        )
        if not credential or not credential.public_key:
            return JsonResponse(
                {'status': 'error', 'message': 'No usable passkey was found. Sign in and register it again.'},
                status=400,
            )

        verified = verify_authentication_response(
            credential=data,
            expected_challenge=challenge['challenge_bytes'],
            expected_rp_id=challenge['rp_id'],
            expected_origin=challenge['origin'],
            credential_public_key=base64url_to_bytes(credential.public_key),
            credential_current_sign_count=credential.sign_count,
            require_user_verification=True,
        )
        credential.sign_count = verified.new_sign_count
        credential.save(update_fields=['sign_count'])
        login(request, credential.user)
        return JsonResponse({
            'status': 'success',
            'message': f'Welcome back, {credential.user.username}!',
            'redirect_url': '/dashboard/',
        })
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        logger.warning('Invalid WebAuthn authentication response: %s', exc)
        return JsonResponse({'status': 'error', 'message': 'Passkey verification failed. Please try again.'}, status=400)
    except WebAuthnException as exc:
        logger.warning('WebAuthn authentication failed: %s', exc)
        return JsonResponse({'status': 'error', 'message': 'Passkey verification failed. Please try again.'}, status=400)


def passkey_register_challenge(request):
    """Create a registration challenge for an existing or new user."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    rp_id, origin = _webauthn_rp_and_origin(request)
    if request.user.is_authenticated:
        user_name = request.user.username
        user_id = str(request.user.pk).encode('utf-8')
        request.session['webauthn_reg_user_id'] = request.user.pk
        credentials = request.user.passkeys.exclude(public_key='')
    else:
        ip = get_client_ip(request) or 'unknown'
        if not rate_limit(f'passkey_signup_{ip}', 5, 3600):
            return JsonResponse({'status': 'error', 'message': 'Too many signup attempts. Please wait and try again.'}, status=429)
        try:
            request_data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid registration request.'}, status=400)
        if not isinstance(request_data, dict):
            return JsonResponse({'status': 'error', 'message': 'Invalid registration request.'}, status=400)
        username = str(request_data.get('username', '')).strip()
        username_field = User._meta.get_field('username')
        try:
            username = username_field.clean(username, None)
        except ValidationError as exc:
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
        if User.objects.filter(username__iexact=username).exists():
            return JsonResponse(
                {'status': 'error', 'message': 'That username is already taken. Choose another or sign in.'},
                status=409,
            )
        user_name = username
        user_id = secrets.token_bytes(32)
        request.session['webauthn_reg_username'] = username
        request.session['webauthn_reg_user_handle'] = _base64url_encode(user_id)
        credentials = PasskeyCredential.objects.none()

    challenge = _new_webauthn_challenge(request, 'webauthn_reg_challenge', rp_id, origin)
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name='SpendWise',
        user_id=user_id,
        user_name=user_name,
        user_display_name=user_name,
        challenge=challenge,
        timeout=60000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item.credential_id))
            for item in credentials
        ],
    )
    return JsonResponse(json.loads(options_to_json(options)))


def passkey_register_verify(request):
    """Verify a registration before storing a credential or creating an account."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    challenge = _take_webauthn_challenge(request, 'webauthn_reg_challenge')
    if not challenge:
        return JsonResponse(
            {'status': 'error', 'message': 'Registration challenge expired. Please try again.'},
            status=400,
        )

    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return JsonResponse({'status': 'error', 'message': 'Invalid passkey response.'}, status=400)
        verified = verify_registration_response(
            credential=data,
            expected_challenge=challenge['challenge_bytes'],
            expected_rp_id=challenge['rp_id'],
            expected_origin=challenge['origin'],
            require_user_verification=True,
        )
        if base64url_to_bytes(data.get('rawId', '')) != verified.credential_id:
            return JsonResponse({'status': 'error', 'message': 'Invalid passkey response.'}, status=400)
        credential_id = _base64url_encode(verified.credential_id)
        device_name = str(data.get('deviceName') or 'Biometric Passkey').strip()[:100]
        user_id = request.session.pop('webauthn_reg_user_id', None)
        username = request.session.pop('webauthn_reg_username', None)
        user_handle = request.session.pop('webauthn_reg_user_handle', None)

        if user_id:
            if not request.user.is_authenticated or request.user.pk != user_id:
                return JsonResponse(
                    {'status': 'error', 'message': 'Sign in again before registering this passkey.'},
                    status=403,
                )
            user = request.user
        else:
            if request.user.is_authenticated or not username or not user_handle:
                return JsonResponse({'status': 'error', 'message': 'Signup expired. Please try again.'}, status=400)
            username_field = User._meta.get_field('username')
            username = username_field.clean(username, None)
            if User.objects.filter(username__iexact=username).exists():
                return JsonResponse(
                    {'status': 'error', 'message': 'That username is already taken. Choose another.'},
                    status=409,
                )

        existing_credential = PasskeyCredential.objects.filter(credential_id=credential_id).first()
        if existing_credential and (not user_id or existing_credential.user_id != user_id):
            return JsonResponse(
                {'status': 'error', 'message': 'This passkey is already linked to another account.'},
                status=409,
            )

        with transaction.atomic():
            if not user_id:
                user = User.objects.create_user(username=username, password=None)
            if existing_credential:
                existing_credential.public_key = _base64url_encode(verified.credential_public_key)
                existing_credential.sign_count = verified.sign_count
                existing_credential.device_name = device_name
                existing_credential.save(update_fields=['public_key', 'sign_count', 'device_name'])
            else:
                PasskeyCredential.objects.create(
                    user=user,
                    credential_id=credential_id,
                    public_key=_base64url_encode(verified.credential_public_key),
                    sign_count=verified.sign_count,
                    device_name=device_name,
                )

        if not user_id:
            login(request, user)
            return JsonResponse({
                'status': 'success',
                'message': 'Your account and passkey are ready!',
                'redirect_url': '/dashboard/',
            })
        return JsonResponse({'status': 'success', 'message': 'Passkey registered successfully!'})
    except IntegrityError:
        return JsonResponse(
            {'status': 'error', 'message': 'That username or passkey is already registered.'},
            status=409,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        logger.warning('Invalid WebAuthn registration response: %s', exc)
        return JsonResponse({'status': 'error', 'message': 'Passkey registration failed. Please try again.'}, status=400)
    except WebAuthnException as exc:
        logger.warning('WebAuthn registration failed: %s', exc)
        return JsonResponse({'status': 'error', 'message': 'Passkey registration failed. Please try again.'}, status=400)
