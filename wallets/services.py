import uuid
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from wallets.models import RechargeStatus, RechargeTransaction, Wallet


def credit_wallet(wallet: Wallet, amount: Decimal) -> Wallet:
    wallet.balance = wallet.balance + amount
    wallet.save(update_fields=["balance", "updated_at"])
    return wallet


def debit_wallet(wallet: Wallet, amount: Decimal) -> bool:
    if wallet.balance < amount:
        return False
    wallet.balance = wallet.balance - amount
    wallet.save(update_fields=["balance", "updated_at"])
    return True


def initiate_recharge(user, amount: Decimal) -> RechargeTransaction:
    if amount <= 0:
        raise ValidationError({"amount": "Amount must be greater than zero."})
    return RechargeTransaction.objects.create(
        user=user,
        amount=amount,
        reference=uuid.uuid4().hex,
        status=RechargeStatus.PENDING,
    )


def process_recharge_callback(reference: str, status: str) -> RechargeTransaction:
    if status not in RechargeStatus.values:
        raise ValidationError({"status": "Invalid recharge status."})

    with transaction.atomic():
        try:
            txn = RechargeTransaction.objects.select_for_update().get(reference=reference)
        except RechargeTransaction.DoesNotExist as exc:
            raise ValidationError({"reference": "Unknown recharge reference."}) from exc

        if txn.status == RechargeStatus.SUCCESS:
            return txn

        if txn.status != RechargeStatus.PENDING:
            raise ValidationError(
                {"status": f"Cannot move recharge from {txn.status} to {status}."}
            )

        if status == RechargeStatus.SUCCESS:
            wallet = Wallet.objects.select_for_update().get(user=txn.user)
            credit_wallet(wallet, txn.amount)
            txn.status = RechargeStatus.SUCCESS
            txn.save(update_fields=["status", "updated_at"])
        elif status == RechargeStatus.FAILED:
            txn.status = RechargeStatus.FAILED
            txn.save(update_fields=["status", "updated_at"])
        else:
            raise ValidationError({"status": "Callback status must be success or failed."})

        return txn
