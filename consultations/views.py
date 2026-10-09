from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from consultations.exceptions import InvalidTransition
from consultations.models import Session
from consultations.serializers import AssignSerializer, SessionCreateSerializer, SessionSerializer
from consultations.services import (
    accept_session,
    assign_session,
    bill_session,
    cancel_session,
    create_session,
    end_session,
    start_session,
)

User = get_user_model()


def _session_for(request, pk) -> Session:
    session = get_object_or_404(Session, pk=pk)
    if session.user_id != request.user.id and session.provider_id != request.user.id:
        raise InvalidTransition("You do not have access to this session.")
    return session


class SessionListCreateView(APIView):
    def post(self, request):
        serializer = SessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = create_session(
            request.user,
            serializer.validated_data.get("per_minute_cost"),
        )
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


class SessionDetailView(APIView):
    def get(self, request, pk):
        session = _session_for(request, pk)
        return Response(SessionSerializer(session).data)


class SessionAssignView(APIView):
    def post(self, request, pk):
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = get_object_or_404(User, pk=serializer.validated_data["provider_id"])
        session = assign_session(pk, request.user, provider)
        return Response(SessionSerializer(session).data)


class SessionAcceptView(APIView):
    def post(self, request, pk):
        session = accept_session(pk, request.user)
        return Response(SessionSerializer(session).data)


class SessionStartView(APIView):
    def post(self, request, pk):
        session = start_session(pk, request.user)
        return Response(SessionSerializer(session).data)


class SessionEndView(APIView):
    def post(self, request, pk):
        session = end_session(pk, request.user)
        return Response(SessionSerializer(session).data)


class SessionBillView(APIView):
    def post(self, request, pk):
        session = bill_session(pk, request.user)
        return Response(SessionSerializer(session).data)


class SessionCancelView(APIView):
    def post(self, request, pk):
        session = cancel_session(pk, request.user)
        return Response(SessionSerializer(session).data)
