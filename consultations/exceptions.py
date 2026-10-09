from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_400_BAD_REQUEST


class InvalidTransition(APIException):
    status_code = HTTP_400_BAD_REQUEST
    default_detail = "Invalid session state transition."
    default_code = "invalid_transition"


class InsufficientBalance(APIException):
    status_code = HTTP_400_BAD_REQUEST
    default_detail = "Insufficient wallet balance."
    default_code = "insufficient_balance"
