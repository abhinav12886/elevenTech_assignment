from django.urls import path

from accounts.views import RegisterView

urlpatterns = [
    path("", RegisterView.as_view(), name="register"),
]
