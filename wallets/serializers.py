from decimal import Decimal

from rest_framework import serializers

from wallets.models import RechargeStatus, RechargeTransaction, Wallet


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("balance",)


class RechargeInitiateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class RechargeTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeTransaction
        fields = ("id", "amount", "reference", "status", "created_at", "updated_at")
        read_only_fields = fields


class RechargeCallbackSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    status = serializers.ChoiceField(choices=RechargeStatus.choices)
