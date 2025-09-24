"""
Authentication and authorization exceptions
"""
from fastapi import HTTPException
from starlette import status


class AuthenticationError(HTTPException):
    """Authentication failed"""
    def __init__(self, detail: str = "Invalid API key"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(HTTPException):
    """Authorization failed"""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class BudgetExceededError(HTTPException):
    """Budget exceeded"""
    def __init__(self, detail: str = "Budget exceeded. Please contact administrator."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )