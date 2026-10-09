from django.urls import path

from wallets.views import RechargeCallbackView, RechargeInitiateView, WalletDetailView

urlpatterns = [
    path("", WalletDetailView.as_view(), name="wallet-detail"),
    path("recharge/", RechargeInitiateView.as_view(), name="wallet-recharge"),
    path("recharge/callback/", RechargeCallbackView.as_view(), name="wallet-recharge-callback"),
]
