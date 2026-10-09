from decimal import Decimal

from rest_framework import serializers

from consultations.models import Session


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = (
            "id",
            "user",
            "provider",
            "status",
            "per_minute_cost",
            "started_at",
            "ended_at",
            "billed_minutes",
            "billed_amount",
            "billable_seconds",
            "ended_by",
            "end_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SessionCreateSerializer(serializers.Serializer):
    per_minute_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        min_value=Decimal("0.01"),
    )


class AssignSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()
