from django.contrib import admin

from wallets.models import RechargeTransaction, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")


@admin.register(RechargeTransaction)
class RechargeTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "amount", "status", "created_at")
    search_fields = ("reference",)
