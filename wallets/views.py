from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from wallets.serializers import (
    RechargeCallbackSerializer,
    RechargeInitiateSerializer,
    RechargeTransactionSerializer,
    WalletSerializer,
)
from wallets.services import initiate_recharge, process_recharge_callback


class WalletDetailView(APIView):
    def get(self, request):
        return Response(WalletSerializer(request.user.wallet).data)


class RechargeInitiateView(APIView):
    def post(self, request):
        serializer = RechargeInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = initiate_recharge(request.user, serializer.validated_data["amount"])
        return Response(RechargeTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


class RechargeCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RechargeCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = process_recharge_callback(
            serializer.validated_data["reference"],
            serializer.validated_data["status"],
        )
        return Response(RechargeTransactionSerializer(txn).data)
