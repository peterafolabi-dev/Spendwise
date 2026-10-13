import csv
import base64
import json
from io import StringIO
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, Client, RequestFactory, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum
from webauthn.helpers.exceptions import WebAuthnException
from .models import Account, Category, Transaction, Budget, RecurringTransaction, PasskeyCredential
from .views import _webauthn_rp_and_origin

class TrackerTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pw')
        self.user2 = User.objects.create_user(username='user2', password='pw')
        
        self.client1 = Client()
        self.client1.login(username='user1', password='pw')
        
        self.client2 = Client()
        self.client2.login(username='user2', password='pw')
        
        self.acc1 = Account.objects.create(user=self.user1, name='Acc1', type='CASH', starting_balance=Decimal('100.00'))
        self.acc2 = Account.objects.create(user=self.user2, name='Acc2', type='CASH', starting_balance=Decimal('200.00'))
        
        self.cat1 = Category.objects.create(user=self.user1, name='Food', type='EXPENSE')

    def test_signup_creates_account_shows_message_and_redirects_to_login(self):
        client = Client()

        response = client.post(
            reverse('signup'),
            {
                'username': 'new-user',
                'password1': 'StrongTestPassword!846',
                'password2': 'StrongTestPassword!846',
            },
            follow=True,
        )

        self.assertEqual(response.redirect_chain, [(reverse('login'), 302)])
        self.assertContains(response, 'Account created successfully. Please sign in.')
        self.assertContains(response, 'data-toast-message')
        self.assertTrue(User.objects.filter(username='new-user').exists())
        self.assertNotIn('_auth_user_id', client.session)

    def test_login_welcomes_user_and_logout_shows_confirmation(self):
        user = User.objects.create_user(
            username='welcome-user',
            password='StrongTestPassword!846',
            first_name='Welcome',
        )
        client = Client()

        login_response = client.post(
            reverse('login'),
            {'username': user.username, 'password': 'StrongTestPassword!846'},
            follow=True,
        )
        self.assertEqual(login_response.redirect_chain, [(reverse('dashboard'), 302)])
        self.assertContains(login_response, 'Welcome back, Welcome!')
        self.assertContains(login_response, 'data-toast-message')

        logout_response = client.get(reverse('logout'), follow=True)
        self.assertEqual(logout_response.redirect_chain, [(reverse('landing'), 302)])
        self.assertContains(logout_response, 'You have been logged out.')
        self.assertContains(logout_response, 'data-toast-message')
        self.assertNotIn('_auth_user_id', client.session)
        
    def test_ownership(self):
        # User 1 should not see User 2's account
        response = self.client1.get(reverse('account_list'))
        self.assertContains(response, 'Acc1')
        self.assertNotContains(response, 'Acc2')
        
    def test_decimal_math_correctness(self):
        Transaction.objects.create(user=self.user1, account=self.acc1, amount=Decimal('10.50'), type='INCOME', date=timezone.now().date())
        Transaction.objects.create(user=self.user1, account=self.acc1, amount=Decimal('5.25'), type='EXPENSE', date=timezone.now().date())
        
        self.assertEqual(self.acc1.current_balance(), Decimal('105.25'))
        
    def test_budget_limit_detection(self):
        budget = Budget.objects.create(user=self.user1, category=self.cat1, limit=Decimal('50.00'))
        self.assertEqual(budget.limit, Decimal('50.00'))
        Transaction.objects.create(user=self.user1, account=self.acc1, category=self.cat1, amount=Decimal('60.00'), type='EXPENSE', date=timezone.now().date())
        total_spent = Transaction.objects.filter(category=self.cat1).aggregate(t=Sum('amount'))['t']
        self.assertTrue(total_spent > budget.limit)

    def test_recurring_transaction_generation(self):
        # No actual generation logic was specified in views, so we'll test the model.
        rt = RecurringTransaction.objects.create(
            user=self.user1, account=self.acc1, amount=Decimal('10.00'), type='EXPENSE',
            category=self.cat1, frequency='MONTHLY', next_due_date=timezone.now().date()
        )
        self.assertEqual(rt.amount, Decimal('10.00'))

    def test_csv_export_escaping(self):
        Transaction.objects.create(
            user=self.user1, account=self.acc1, amount=Decimal('10.00'), type='EXPENSE',
            category=self.cat1, date=timezone.now().date(), note='=CMD()'
        )
        response = self.client1.get(reverse('export_csv'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("'=CMD()", content)

    def test_csv_import_malformed_rows(self):
        csv_data = "Date,Account,Type,Category,Amount,Note\n2023-01-01,Acc1,EXPENSE,Food,bad_amount,Note1"
        f = StringIO(csv_data)
        f.name = "test.csv"
        
        response = self.client1.post(reverse('import_csv'), {'csv_file': f})
        # bad_amount row should be skipped, so 0 new transactions
        self.assertEqual(Transaction.objects.count(), 0)

    def test_category_deletion_fallback(self):
        Transaction.objects.create(user=self.user1, account=self.acc1, amount=Decimal('10.00'), type='EXPENSE', category=self.cat1, date=timezone.now().date())
        response = self.client1.post(reverse('category_delete', args=[self.cat1.id]))
        self.assertEqual(response.status_code, 302)
        
        # Check fallback
        self.assertFalse(Category.objects.filter(id=self.cat1.id).exists())
        fallback = Category.objects.get(name='Uncategorised', user=self.user1)
        t = Transaction.objects.first()
        self.assertEqual(t.category, fallback)

    def test_transaction_search_type_account_and_date_filters(self):
        Transaction.objects.create(
            user=self.user1, account=self.acc1, category=self.cat1,
            amount=Decimal('25.00'), type='EXPENSE',
            date=timezone.now().date(), note='Market groceries',
        )
        Transaction.objects.create(
            user=self.user1, account=self.acc1,
            amount=Decimal('90.00'), type='INCOME',
            date=timezone.now().date(), note='Payday',
        )

        response = self.client1.get(reverse('transaction_list'), {
            'q': 'Market', 'type': 'EXPENSE', 'account': self.acc1.pk,
            'date_from': timezone.now().date().isoformat(),
            'date_to': timezone.now().date().isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['object_list'].values_list('note', flat=True)), ['Market groceries'])

    def test_budget_list_reports_real_monthly_spending(self):
        budget = Budget.objects.create(user=self.user1, category=self.cat1, limit=Decimal('50.00'))
        Transaction.objects.create(
            user=self.user1, account=self.acc1, category=self.cat1,
            amount=Decimal('60.00'), type='EXPENSE', date=timezone.now().date(),
        )
        Transaction.objects.create(
            user=self.user2, account=self.acc2, category=Category.objects.create(
                user=self.user2, name='Food', type='EXPENSE',
            ),
            amount=Decimal('100.00'), type='EXPENSE', date=timezone.now().date(),
        )

        response = self.client1.get(reverse('budget_list'))
        budget_in_context = next(item for item in response.context['object_list'] if item.pk == budget.pk)

        self.assertEqual(budget_in_context.spent, Decimal('60.00'))
        self.assertEqual(budget_in_context.overage, Decimal('10.00'))
        self.assertTrue(budget_in_context.is_over_limit)
        self.assertContains(response, 'Budget exceeded by ₦10.00')

    def test_passkey_authentication_rejects_invalid_signature(self):
        credential_id = base64.urlsafe_b64encode(b'test-credential').decode().rstrip('=')
        PasskeyCredential.objects.create(
            user=self.user1, credential_id=credential_id,
            public_key=base64.urlsafe_b64encode(b'public-key').decode().rstrip('='),
        )
        client = Client()
        client.post(reverse('passkey_challenge'), data='{}', content_type='application/json')

        with patch('tracker.views.verify_authentication_response', side_effect=WebAuthnException('bad signature')):
            response = client.post(
                reverse('passkey_verify'),
                data=json.dumps({'id': credential_id, 'rawId': credential_id, 'response': {}}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn('_auth_user_id', client.session)

    def test_passwordless_signup_creates_account_only_after_verification(self):
        client = Client()
        challenge_response = client.post(
            reverse('passkey_register_challenge'),
            data=json.dumps({'username': 'passkey-user'}),
            content_type='application/json',
        )
        self.assertEqual(challenge_response.status_code, 200)
        self.assertEqual(
            challenge_response.json()['authenticatorSelection']['authenticatorAttachment'],
            'platform',
        )
        self.assertEqual(
            challenge_response.json()['authenticatorSelection']['residentKey'],
            'required',
        )
        self.assertFalse(User.objects.filter(username='passkey-user').exists())

        verified = SimpleNamespace(
            credential_id=b'passkey-credential',
            credential_public_key=b'verified-public-key',
            sign_count=1,
        )
        with patch('tracker.views.verify_registration_response', return_value=verified):
            response = client.post(
                reverse('passkey_register_verify'),
                data=json.dumps({
                    'id': base64.urlsafe_b64encode(b'passkey-credential').decode().rstrip('='),
                    'rawId': base64.urlsafe_b64encode(b'passkey-credential').decode().rstrip('='),
                    'response': {'attestationObject': 'test', 'clientDataJSON': 'test'},
                    'deviceName': 'Test device',
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username='passkey-user')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(PasskeyCredential.objects.filter(user=user, sign_count=1).exists())
        self.assertEqual(response.json()['redirect_url'], '/login/')
        self.assertNotIn('_auth_user_id', client.session)
        login_page = client.get(reverse('login'))
        self.assertContains(login_page, 'Account created successfully with your passkey. Please sign in.')

    def test_existing_user_can_add_a_verified_passkey(self):
        client = Client()
        client.force_login(self.user1)
        credential_id = base64.urlsafe_b64encode(b'existing-user-credential').decode().rstrip('=')
        legacy_credential = PasskeyCredential.objects.create(
            user=self.user1,
            credential_id=credential_id,
            public_key='',
        )
        challenge_response = client.post(
            reverse('passkey_register_challenge'),
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(challenge_response.status_code, 200)
        self.assertFalse(challenge_response.json().get('excludeCredentials'))

        verified = SimpleNamespace(
            credential_id=b'existing-user-credential',
            credential_public_key=b'verified-key',
            sign_count=0,
        )
        with patch('tracker.views.verify_registration_response', return_value=verified):
            response = client.post(
                reverse('passkey_register_verify'),
                data=json.dumps({
                    'id': credential_id,
                    'rawId': credential_id,
                    'response': {'attestationObject': 'test', 'clientDataJSON': 'test'},
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PasskeyCredential.objects.filter(user=self.user1).count(), 1)
        legacy_credential.refresh_from_db()
        self.assertEqual(
            legacy_credential.public_key,
            base64.urlsafe_b64encode(b'verified-key').decode().rstrip('='),
        )

    def test_dashboard_uses_recorded_spending_and_recurring_bills(self):
        self.acc1.starting_balance = Decimal('100.00')
        self.acc1.save(update_fields=['starting_balance'])
        Budget.objects.create(user=self.user1, category=self.cat1, limit=Decimal('100.00'))
        today = timezone.localdate()
        Transaction.objects.create(
            user=self.user1, account=self.acc1, category=self.cat1,
            amount=Decimal('25.00'), type='EXPENSE', date=today,
        )
        Transaction.objects.create(
            user=self.user1, account=self.acc1,
            amount=Decimal('50.00'), type='EXPENSE', date=today,
        )
        RecurringTransaction.objects.create(
            user=self.user1, account=self.acc1, amount=Decimal('10.00'),
            type='EXPENSE', frequency='MONTHLY', next_due_date=today,
        )

        response = self.client1.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'date-range-dropdown-wrapper')
        self.assertNotContains(response, 'Oct 2026')
        self.assertNotContains(response, 'Zero duplicate charges')
        self.assertEqual(response.context['total_balance'], Decimal('25.00'))
        self.assertEqual(response.context['monthly_expenses'], Decimal('75.00'))
        self.assertEqual(response.context['budget_remaining'], Decimal('65.00'))
        self.assertEqual(
            response.context['safe_to_spend_today'],
            Decimal('65.00') / Decimal(response.context['days_left']),
        )
        self.assertEqual(
            json.loads(response.context['cat_data_json']),
            [{'label': 'Food', 'value': 25.0, 'icon': '', 'color': '#10b981'}],
        )
        forecast = json.loads(response.context['forecast_json'])
        self.assertEqual(len(forecast), 4)
        self.assertEqual(forecast[0]['balance'], 25.0)
        self.assertEqual(forecast[-1]['balance'], -50.0)

    def test_copilot_uses_authenticated_users_real_financial_data(self):
        self.acc1.starting_balance = Decimal('50000.00')
        self.acc1.save(update_fields=['starting_balance'])
        Transaction.objects.create(
            user=self.user1, account=self.acc1, category=self.cat1,
            amount=Decimal('28500.00'), type='EXPENSE', date=timezone.localdate(),
        )

        greeting = self.client1.get(reverse('copilot_context'))
        answer = self.client1.post(
            reverse('copilot_chat_api'),
            data=json.dumps({'message': 'What was my top spending this month?'}),
            content_type='application/json',
        )

        self.assertEqual(greeting.status_code, 200)
        self.assertIn('₦21,500.00', greeting.json()['greeting'])
        self.assertIn('Food at ₦28,500.00', greeting.json()['greeting'])
        self.assertEqual(answer.status_code, 200)
        self.assertIn('₦28,500.00', answer.json()['reply'])
        self.assertNotIn('**', answer.json()['reply'])

    def test_passkey_challenge_uses_https_origin_from_render_proxy(self):
        request = RequestFactory().post(
            '/api/passkey/challenge/',
            HTTP_HOST='spendwise.example.com',
            HTTP_X_FORWARDED_PROTO='https',
        )
        with override_settings(ALLOWED_HOSTS=['spendwise.example.com']):
            self.assertEqual(
                _webauthn_rp_and_origin(request),
                ('spendwise.example.com', 'https://spendwise.example.com'),
            )

    def test_passkey_authentication_only_offers_local_platform_credentials(self):
        credential_id = base64.urlsafe_b64encode(b'platform-credential').decode().rstrip('=')
        PasskeyCredential.objects.create(
            user=self.user1,
            credential_id=credential_id,
            public_key=base64.urlsafe_b64encode(b'public-key').decode().rstrip('='),
        )

        response = Client().post(
            reverse('passkey_challenge'),
            data='{}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        options = response.json()
        self.assertEqual(options['hints'], ['client-device'])
        self.assertEqual(options['userVerification'], 'required')
        self.assertEqual(
            options['allowCredentials'],
            [{
                'type': 'public-key',
                'id': credential_id,
                'transports': ['internal'],
            }],
        )

    def test_passkey_authentication_requires_a_registered_credential(self):
        response = Client().post(
            reverse('passkey_challenge'),
            data='{}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('platform passkey', response.json()['message'])

    def test_login_page_exposes_passkey_feedback_and_script(self):
        response = Client().get(reverse('login'))

        self.assertContains(response, 'Sign in with Passkey / Face ID / Touch ID')
        self.assertContains(response, 'secure passkey handoff, not a website link')
        self.assertContains(response, 'id="passkey-status"')
        self.assertContains(response, 'spendwise-features.')
        self.assertNotContains(response, '>Google</button>')
        self.assertNotContains(response, '>Apple</button>')
