from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    path('accounts/', views.AccountListView.as_view(), name='account_list'),
    path('accounts/create/', views.AccountCreateView.as_view(), name='account_create'),
    path('accounts/<int:pk>/update/', views.AccountUpdateView.as_view(), name='account_update'),
    path('accounts/<int:pk>/delete/', views.AccountDeleteView.as_view(), name='account_delete'),
    
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/update/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete_view, name='category_delete'),
    
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('transactions/create/', views.TransactionCreateView.as_view(), name='transaction_create'),
    path('transactions/<int:pk>/update/', views.TransactionUpdateView.as_view(), name='transaction_update'),
    path('transactions/<int:pk>/delete/', views.TransactionDeleteView.as_view(), name='transaction_delete'),
    path('transactions/quick-add/', views.quick_add_transaction, name='quick_add_transaction'),
    
    path('budgets/', views.BudgetListView.as_view(), name='budget_list'),
    path('budgets/create/', views.BudgetCreateView.as_view(), name='budget_create'),
    path('budgets/<int:pk>/update/', views.BudgetUpdateView.as_view(), name='budget_update'),
    path('budgets/<int:pk>/delete/', views.BudgetDeleteView.as_view(), name='budget_delete'),
    
    path('savings/', views.SavingsGoalListView.as_view(), name='savings_list'),
    path('savings/create/', views.SavingsGoalCreateView.as_view(), name='savings_create'),
    path('savings/<int:pk>/update/', views.SavingsGoalUpdateView.as_view(), name='savings_update'),
    path('savings/<int:pk>/delete/', views.SavingsGoalDeleteView.as_view(), name='savings_delete'),
    
    path('recurring/', views.RecurringListView.as_view(), name='recurring_list'),
    path('recurring/create/', views.RecurringCreateView.as_view(), name='recurring_create'),
    path('recurring/<int:pk>/update/', views.RecurringUpdateView.as_view(), name='recurring_update'),
    path('recurring/<int:pk>/delete/', views.RecurringDeleteView.as_view(), name='recurring_delete'),
    
    path('reports/', views.reports_view, name='reports'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('import/csv/', views.import_csv, name='import_csv'),
    
    path('profile/', views.profile_view, name='profile'),
    
    # Passkey / WebAuthn
    path('api/passkey/challenge/', views.passkey_challenge, name='passkey_challenge'),
    path('api/passkey/verify/', views.passkey_verify, name='passkey_verify'),
    path('api/passkey/register/challenge/', views.passkey_register_challenge, name='passkey_register_challenge'),
    path('api/passkey/register/verify/', views.passkey_register_verify, name='passkey_register_verify'),
]

