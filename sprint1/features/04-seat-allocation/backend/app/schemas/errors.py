from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException


class ErrorCode(str, Enum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MAX_SEATS_EXCEEDED = "MAX_SEATS_EXCEEDED"
    SHOW_NOT_BOOKABLE = "SHOW_NOT_BOOKABLE"
    SEATS_UNAVAILABLE = "SEATS_UNAVAILABLE"
    HOLD_EXPIRED = "HOLD_EXPIRED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable calm explanation")
    details: Optional[Any] = Field(default=None, description="Detailed context payload, e.g. failed seat IDs")


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppAPIException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: Optional[Any] = None,
        headers: Optional[dict] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code.value,
                    "message": message,
                    "details": details
                }
            },
            headers=headers
        )
        self.error_code = code
        self.error_message = message
        self.error_details = details
