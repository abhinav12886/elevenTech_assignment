from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import UserRole

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "email", "password", "role")

    def validate_role(self, value):
        if value not in UserRole.values:
            raise serializers.ValidationError("Invalid role.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data.get("role", UserRole.USER),
        )
