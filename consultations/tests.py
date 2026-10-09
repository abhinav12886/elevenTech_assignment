from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserRole
from consultations.models import SessionStatus
from wallets.models import RechargeStatus, Wallet

User = get_user_model()
RATE = Decimal("50.00")


class BRDScenariosTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            role=UserRole.USER,
        )
        self.provider = User.objects.create_user(
            email="provider@example.com",
            password="password123",
            role=UserRole.PROVIDER,
        )
        self.user_token = self._token("user@example.com")
        self.provider_token = self._token("provider@example.com")

    def _token(self, email):
        response = self.client.post(
            "/api/auth/token/",
            {"email": email, "password": "password123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.data["access"]

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _recharge(self, amount, token=None):
        self._auth(token or self.user_token)
        response = self.client.post(
            "/api/wallet/recharge/",
            {"amount": str(amount)},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        reference = response.data["reference"]
        callback = self.client.post(
            "/api/wallet/recharge/callback/",
            {"reference": reference, "status": RechargeStatus.SUCCESS},
            format="json",
        )
        self.assertEqual(callback.status_code, 200)
        return reference

    def _create_accepted_session(self):
        self._auth(self.user_token)
        created = self.client.post(
            "/api/sessions/",
            {"per_minute_cost": str(RATE)},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        session_id = created.data["id"]
        assigned = self.client.post(
            f"/api/sessions/{session_id}/assign/",
            {"provider_id": self.provider.id},
            format="json",
        )
        self.assertEqual(assigned.status_code, 200)
        self._auth(self.provider_token)
        accepted = self.client.post(f"/api/sessions/{session_id}/accept/", format="json")
        self.assertEqual(accepted.status_code, 200)
        return session_id

    def test_insufficient_balance_cannot_start(self):
        self._recharge(Decimal("200.00"))
        session_id = self._create_accepted_session()
        self._auth(self.user_token)
        start = self.client.post(f"/api/sessions/{session_id}/start/", format="json")
        self.assertEqual(start.status_code, 400)
        detail = self.client.get(f"/api/sessions/{session_id}/")
        self.assertEqual(detail.data["status"], SessionStatus.ACCEPTED_BY_PROVIDER)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("200.00"))

    def test_happy_path_bills_two_minutes(self):
        self._recharge(Decimal("250.00"))
        session_id = self._create_accepted_session()
        started_at = timezone.now()
        self._auth(self.user_token)
        with patch("consultations.services.timezone.now", return_value=started_at):
            start = self.client.post(f"/api/sessions/{session_id}/start/", format="json")
            self.assertEqual(start.status_code, 200)
            first_bill = self.client.post(f"/api/sessions/{session_id}/bill/", format="json")
            self.assertEqual(first_bill.status_code, 200)
            self.assertEqual(first_bill.data["billed_minutes"], 1)

        later = started_at + timedelta(seconds=60)
        with patch("consultations.services.timezone.now", return_value=later):
            second_bill = self.client.post(f"/api/sessions/{session_id}/bill/", format="json")
            self.assertEqual(second_bill.status_code, 200)
            self.assertEqual(second_bill.data["billed_minutes"], 2)
            ended = self.client.post(f"/api/sessions/{session_id}/end/", format="json")
            self.assertEqual(ended.status_code, 200)
            self.assertEqual(ended.data["status"], SessionStatus.COMPLETED)

        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("150.00"))
        self.assertEqual(ended.data["billed_amount"], "100.00")

    def test_balance_runs_out_ends_session(self):
        self._recharge(Decimal("290.00"))
        session_id = self._create_accepted_session()
        started_at = timezone.now()
        self._auth(self.user_token)
        with patch("consultations.services.timezone.now", return_value=started_at):
            start = self.client.post(f"/api/sessions/{session_id}/start/", format="json")
            self.assertEqual(start.status_code, 200)

        later = started_at + timedelta(seconds=4 * 60)
        with patch("consultations.services.timezone.now", return_value=later):
            billed = self.client.post(f"/api/sessions/{session_id}/bill/", format="json")
            self.assertEqual(billed.status_code, 200)
            self.assertEqual(billed.data["billed_minutes"], 5)
            self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("40.00"))

        next_minute = started_at + timedelta(seconds=5 * 60)
        with patch("consultations.services.timezone.now", return_value=next_minute):
            exhausted = self.client.post(f"/api/sessions/{session_id}/bill/", format="json")
            self.assertEqual(exhausted.status_code, 200)
            self.assertEqual(exhausted.data["status"], SessionStatus.COMPLETED)
            self.assertEqual(exhausted.data["ended_by"], "system")
            self.assertEqual(exhausted.data["end_reason"], "Insufficient Balance")
            self.assertGreaterEqual(exhausted.data["billable_seconds"], 300)

        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal("40.00"))
        self.assertGreaterEqual(wallet.balance, Decimal("0.00"))

    def test_invalid_state_transition_end_before_start(self):
        self._auth(self.user_token)
        created = self.client.post("/api/sessions/", format="json")
        self.assertEqual(created.status_code, 201)
        ended = self.client.post(f"/api/sessions/{created.data['id']}/end/", format="json")
        self.assertEqual(ended.status_code, 400)

    def test_duplicate_recharge_callback_credits_once(self):
        self._auth(self.user_token)
        initiate = self.client.post(
            "/api/wallet/recharge/",
            {"amount": "100.00"},
            format="json",
        )
        reference = initiate.data["reference"]
        payload = {"reference": reference, "status": RechargeStatus.SUCCESS}
        first = self.client.post("/api/wallet/recharge/callback/", payload, format="json")
        second = self.client.post("/api/wallet/recharge/callback/", payload, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("100.00"))

    def test_duplicate_billing_does_not_double_charge(self):
        self._recharge(Decimal("250.00"))
        session_id = self._create_accepted_session()
        started_at = timezone.now()
        self._auth(self.user_token)
        with patch("consultations.services.timezone.now", return_value=started_at):
            self.client.post(f"/api/sessions/{session_id}/start/", format="json")
            first = self.client.post(f"/api/sessions/{session_id}/bill/", format="json")
            second = self.client.post(f"/api/sessions/{session_id}/bill/", format="json")
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(first.data["billed_minutes"], 1)
            self.assertEqual(second.data["billed_minutes"], 1)

        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("200.00"))
