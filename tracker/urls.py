from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transactions/', views.transactions, name='transactions'),
    path('accounts/', views.accounts, name='accounts'),
    path('categories/', views.categories, name='categories'),
    path('budgets/', views.budgets, name='budgets'),
    path('reports/', views.reports, name='reports'),
    path('savings-goals/', views.savings_goals, name='savings_goals'),
    path('recurring/', views.recurring_transactions, name='recurring_transactions'),
    path('profile/', views.profile, name='profile'),
]
