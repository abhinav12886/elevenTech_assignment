from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.models import UserRole
from consultations.exceptions import InsufficientBalance, InvalidTransition
from consultations.models import BillingTick, EndedBy, Session, SessionStatus
from wallets.models import Wallet
from wallets.services import debit_wallet

CANCELLABLE_STATUSES = {
    SessionStatus.UNASSIGNED,
    SessionStatus.ASSIGNED,
    SessionStatus.ACCEPTED_BY_PROVIDER,
}


def _locked_session(session_id: int) -> Session:
    try:
        return Session.objects.select_for_update().get(pk=session_id)
    except Session.DoesNotExist as exc:
        raise Http404("Session not found.") from exc


def minutes_due(session: Session, now) -> int:
    elapsed = (now - session.started_at).total_seconds()
    if elapsed < 0:
        elapsed = 0
    return int(elapsed // 60) + 1


def _complete_session(session: Session, ended_by: str, reason: str, now) -> Session:
    session.status = SessionStatus.COMPLETED
    session.ended_at = now
    session.ended_by = ended_by
    session.end_reason = reason
    if session.started_at:
        session.billable_seconds = max(0, int((now - session.started_at).total_seconds()))
    session.save(
        update_fields=[
            "status",
            "ended_at",
            "ended_by",
            "end_reason",
            "billable_seconds",
            "billed_minutes",
            "billed_amount",
            "updated_at",
        ]
    )
    return session


def create_session(user, per_minute_cost: Decimal | None = None) -> Session:
    if user.role != UserRole.USER:
        raise PermissionDenied("Only users can create consultation sessions.")
    cost = per_minute_cost if per_minute_cost is not None else Decimal(settings.DEFAULT_PER_MINUTE_COST)
    if cost <= 0:
        raise InvalidTransition("Per-minute cost must be greater than zero.")
    return Session.objects.create(user=user, per_minute_cost=cost)


def assign_session(session_id: int, user, provider) -> Session:
    with transaction.atomic():
        session = _locked_session(session_id)
        if session.user_id != user.id:
            raise PermissionDenied("Only the session owner can assign a provider.")
        if session.status != SessionStatus.UNASSIGNED:
            raise InvalidTransition("Session can only be assigned from unassigned.")
        if provider.role != UserRole.PROVIDER:
            raise InvalidTransition("Assigned account must have the PROVIDER role.")
        session.provider = provider
        session.status = SessionStatus.ASSIGNED
        session.save(update_fields=["provider", "status", "updated_at"])
        return session


def accept_session(session_id: int, user) -> Session:
    with transaction.atomic():
        session = _locked_session(session_id)
        if session.provider_id != user.id:
            raise PermissionDenied("Only the assigned provider can accept this session.")
        if session.status != SessionStatus.ASSIGNED:
            raise InvalidTransition("Session can only be accepted from assigned.")
        session.status = SessionStatus.ACCEPTED_BY_PROVIDER
        session.save(update_fields=["status", "updated_at"])
        return session


def start_session(session_id: int, user, now=None) -> Session:
    now = now or timezone.now()
    with transaction.atomic():
        session = _locked_session(session_id)
        if session.user_id != user.id:
            raise PermissionDenied("Only the session owner can start the session.")
        if session.status != SessionStatus.ACCEPTED_BY_PROVIDER:
            raise InvalidTransition("Session can only be started after the provider has accepted.")
        if Session.objects.select_for_update().filter(
            user=user,
            status=SessionStatus.IN_PROGRESS,
        ).exists():
            raise InvalidTransition("A user cannot have more than one in-progress session.")

        wallet = Wallet.objects.select_for_update().get(user=user)
        required = session.per_minute_cost * settings.MINUTES_REQUIRED_TO_START
        if wallet.balance < required:
            raise InsufficientBalance(
                f"Wallet balance must be at least {required} ({settings.MINUTES_REQUIRED_TO_START} minutes) to start."
            )

        session.status = SessionStatus.IN_PROGRESS
        session.started_at = now
        session.save(update_fields=["status", "started_at", "updated_at"])
        return session


def bill_session(session_id: int, actor, now=None) -> Session:
    now = now or timezone.now()
    with transaction.atomic():
        session = _locked_session(session_id)
        _assert_can_bill_or_end(session, actor)
        if session.status != SessionStatus.IN_PROGRESS:
            raise InvalidTransition("Billing is only allowed while the session is in progress.")
        return _bill_locked_session(session, now)


def _assert_can_bill_or_end(session: Session, actor) -> None:
    if actor is None:
        return
    if session.user_id == actor.id or session.provider_id == actor.id:
        return
    raise PermissionDenied("Only the session user or assigned provider can perform this action.")


def _bill_locked_session(session: Session, now) -> Session:
    wallet = Wallet.objects.select_for_update().get(user_id=session.user_id)
    due = minutes_due(session, now)
    existing = set(
        BillingTick.objects.filter(session=session).values_list("minute_index", flat=True)
    )
    for minute_index in range(due):
        if minute_index in existing:
            continue
        if not debit_wallet(wallet, session.per_minute_cost):
            return _complete_session(
                session,
                EndedBy.SYSTEM,
                settings.INSUFFICIENT_BALANCE_REASON,
                now,
            )
        BillingTick.objects.create(
            session=session,
            minute_index=minute_index,
            amount=session.per_minute_cost,
        )
        session.billed_minutes += 1
        session.billed_amount += session.per_minute_cost
        existing.add(minute_index)
    session.save(update_fields=["billed_minutes", "billed_amount", "updated_at"])
    return session


def end_session(session_id: int, actor, now=None) -> Session:
    now = now or timezone.now()
    with transaction.atomic():
        session = _locked_session(session_id)
        _assert_can_bill_or_end(session, actor)
        if session.status != SessionStatus.IN_PROGRESS:
            raise InvalidTransition("Session can only be ended while it is in progress.")

        session = _bill_locked_session(session, now)
        if session.status != SessionStatus.IN_PROGRESS:
            return session

        if actor.role == UserRole.PROVIDER and session.provider_id == actor.id:
            ended_by = EndedBy.PROVIDER
        else:
            ended_by = EndedBy.USER
        return _complete_session(session, ended_by, "Ended by participant", now)


def cancel_session(session_id: int, user) -> Session:
    with transaction.atomic():
        session = _locked_session(session_id)
        if session.user_id != user.id and session.provider_id != user.id:
            raise PermissionDenied("Only a session participant can cancel.")
        if session.status not in CANCELLABLE_STATUSES:
            raise InvalidTransition("Session cannot be cancelled in its current state.")
        session.status = SessionStatus.CANCELLED
        session.ended_by = EndedBy.USER if session.user_id == user.id else EndedBy.PROVIDER
        session.end_reason = "Cancelled"
        session.save(update_fields=["status", "ended_by", "end_reason", "updated_at"])
        return session
