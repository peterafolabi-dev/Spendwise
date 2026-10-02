from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('landing')
    return redirect('dashboard')

@login_required
def dashboard(request):
    return render(request, 'tracker/dashboard.html')

@login_required
def transactions(request):
    return render(request, 'tracker/transactions.html')

@login_required
def accounts(request):
    return render(request, 'tracker/accounts.html')

@login_required
def categories(request):
    return render(request, 'tracker/categories.html')

@login_required
def budgets(request):
    return render(request, 'tracker/budgets.html')

@login_required
def reports(request):
    return render(request, 'tracker/reports.html')

@login_required
def savings_goals(request):
    return render(request, 'tracker/savings_goals.html')

@login_required
def recurring_transactions(request):
    return render(request, 'tracker/recurring_transactions.html')

@login_required
def profile(request):
    return render(request, 'tracker/profile.html')
