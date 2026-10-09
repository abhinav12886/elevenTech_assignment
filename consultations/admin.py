from django.contrib import admin

from consultations.models import BillingTick, Session


class BillingTickInline(admin.TabularInline):
    model = BillingTick
    extra = 0


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "provider", "status", "billed_minutes", "billed_amount")
    inlines = [BillingTickInline]
