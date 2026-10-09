from django.urls import path

from consultations.views import (
    SessionAcceptView,
    SessionAssignView,
    SessionBillView,
    SessionCancelView,
    SessionDetailView,
    SessionEndView,
    SessionListCreateView,
    SessionStartView,
)

urlpatterns = [
    path("", SessionListCreateView.as_view(), name="session-create"),
    path("<int:pk>/", SessionDetailView.as_view(), name="session-detail"),
    path("<int:pk>/assign/", SessionAssignView.as_view(), name="session-assign"),
    path("<int:pk>/accept/", SessionAcceptView.as_view(), name="session-accept"),
    path("<int:pk>/start/", SessionStartView.as_view(), name="session-start"),
    path("<int:pk>/end/", SessionEndView.as_view(), name="session-end"),
    path("<int:pk>/bill/", SessionBillView.as_view(), name="session-bill"),
    path("<int:pk>/cancel/", SessionCancelView.as_view(), name="session-cancel"),
]
