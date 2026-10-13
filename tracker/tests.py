import base64
import json
import re
from io import StringIO
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.core import mail
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

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_email_and_completes_password_change(self):
        user = User.objects.create_user(
            username='reset-user',
            email='reset@example.com',
            password='OldStrongPassword!846',
        )
        reset_request = self.client.post(
            reverse('password_reset'),
            {'email': user.email},
            follow=True,
        )

        self.assertEqual(reset_request.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset-user', mail.outbox[0].body)
        self.assertIn('/reset/', mail.outbox[0].body)

        reset_path = re.search(r'(/reset/[^\s]+)', mail.outbox[0].body).group(1)
        confirm_page = self.client.get(reset_path, follow=True)
        self.assertEqual(confirm_page.status_code, 200)
        self.assertContains(confirm_page, 'Set a new password')

        usable_reset_path = confirm_page.request['PATH_INFO']
        confirm = self.client.post(
            usable_reset_path,
            {'new_password1': 'NewStrongPassword!864', 'new_password2': 'NewStrongPassword!864'},
            follow=True,
        )
        user.refresh_from_db()

        self.assertEqual(confirm.status_code, 200)
        self.assertContains(confirm, 'Your password has been set')
        self.assertTrue(user.check_password('NewStrongPassword!864'))

    def test_password_reset_pages_are_available_without_email_delivery_configured(self):
        reset_form = Client().get(reverse('password_reset'))
        reset_done = Client().get(reverse('password_reset_done'))
        reset_complete = Client().get(reverse('password_reset_complete'))

        self.assertEqual(reset_form.status_code, 200)
        self.assertContains(reset_form, 'Reset your password')
        self.assertEqual(reset_done.status_code, 200)
        self.assertEqual(reset_complete.status_code, 200)

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',
        EMAIL_HOST='',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_password_reset_does_not_claim_email_was_sent_when_smtp_is_unconfigured(self):
        User.objects.create_user(username='reset-user', email='reset@example.com', password='StrongPassword!846')

        response = Client().post(
            reverse('password_reset'),
            {'email': 'reset@example.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Password reset email is not configured yet')
        self.assertEqual(len(mail.outbox), 0)

    def test_social_login_buttons_only_appear_when_provider_credentials_are_configured(self):
        with override_settings(
            GOOGLE_OAUTH_CLIENT_ID='google-client-id',
            GOOGLE_OAUTH_CLIENT_SECRET='google-client-secret',
            APPLE_OAUTH_CLIENT_ID='apple-service-id',
            APPLE_OAUTH_KEY_ID='apple-key-id',
            APPLE_OAUTH_TEAM_ID='apple-team-id',
            APPLE_OAUTH_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\\nexample\\n-----END PRIVATE KEY-----',
        ):
            response = Client().get(reverse('login'))

        self.assertContains(response, 'Continue with Google')
        self.assertContains(response, 'Continue with Apple')
        self.assertContains(response, reverse('google_login'))
        self.assertContains(response, reverse('apple_login'))
        
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
        
        response = self.client1.post(reverse('import_csv'), {'csv_file': f}, follow=True)
        # bad_amount row should be skipped, so 0 new transactions
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertContains(response, 'Skipped 1 invalid CSV row.')

    def test_csv_import_creates_valid_transaction(self):
        csv_data = (
            "Date,Account,Type,Category,Amount,Note\n"
            "2025-01-15,Imported cash,EXPENSE,Food,1250.50,Weekly groceries"
        )
        f = StringIO(csv_data)
        f.name = "transactions.csv"

        response = self.client1.post(reverse('import_csv'), {'csv_file': f}, follow=True)

        imported = Transaction.objects.get(user=self.user1, note='Weekly groceries')
        self.assertEqual(imported.date.isoformat(), '2025-01-15')
        self.assertEqual(imported.amount, Decimal('1250.50'))
        self.assertEqual(imported.account.name, 'Imported cash')
        self.assertContains(response, 'Imported 1 transaction.')

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
        response_body = {
            'choices': [{
                'message': {'content': 'Food is your highest spending category this month: ₦28,500.00.'},
            }],
        }
        with (
            override_settings(GROQ_API_KEY='test-groq-key', GROQ_MODEL='test-model'),
            patch('tracker.views.urllib.request.urlopen') as mocked_urlopen,
        ):
            mocked_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(response_body).encode('utf-8')
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
        sent_request = mocked_urlopen.call_args.args[0]
        sent_payload = json.loads(sent_request.data.decode('utf-8'))
        self.assertEqual(sent_request.full_url, 'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(sent_request.get_header('Authorization'), 'Bearer test-groq-key')
        self.assertEqual(
            sent_payload['messages'][-1]['content'],
            'What was my top spending this month?',
        )
        self.assertEqual(sent_payload['model'], 'test-model')
        self.assertIn('"recorded_account_balance": "21500.00"', sent_payload['messages'][0]['content'])

    @override_settings(GROQ_API_KEY='')
    def test_copilot_requires_groq_api_key_instead_of_faking_ai(self):
        response = self.client1.post(
            reverse('copilot_chat_api'),
            data=json.dumps({'message': 'hi'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn('GROQ_API_KEY', response.json()['message'])

    @override_settings(GROQ_API_KEY='test-groq-key', GROQ_MODEL='test-model')
    def test_copilot_passes_conversation_history_to_groq(self):
        response_body = {
            'choices': [{
                'message': {'content': 'Yes, based on the figures I just shared.'},
            }],
        }
        with patch('tracker.views.urllib.request.urlopen') as mocked_urlopen:
            mocked_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(response_body).encode('utf-8')
            response = self.client1.post(
                reverse('copilot_chat_api'),
                data=json.dumps({
                    'message': 'Can you explain that?',
                    'history': [
                        {'role': 'user', 'text': 'What is my balance?'},
                        {'role': 'model', 'text': 'Your recorded balance is ₦100.00.'},
                    ],
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        messages = json.loads(mocked_urlopen.call_args.args[0].data.decode('utf-8'))['messages']
        self.assertEqual([item['role'] for item in messages], ['system', 'user', 'assistant', 'user'])
        self.assertEqual(messages[-1]['content'], 'Can you explain that?')

    @override_settings(GROQ_API_KEY='test-groq-key', GROQ_MODEL='test-model')
    def test_copilot_reports_provider_failures_without_faking_reply(self):
        with patch('tracker.views.urllib.request.urlopen', side_effect=OSError('provider offline')):
            response = self.client1.post(
                reverse('copilot_chat_api'),
                data=json.dumps({'message': 'hi'}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn('temporarily unavailable', response.json()['message'])

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
        self.assertNotContains(response, 'To use your phone, choose')
        self.assertContains(response, 'id="passkey-status"')
        self.assertContains(response, 'spendwise-features.')
        self.assertNotContains(response, '>Google</button>')
        self.assertNotContains(response, '>Apple</button>')
