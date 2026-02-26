"""Custom exception classes for FLOW application"""


class FLOWException(Exception):
    """Base exception for FLOW application"""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationException(FLOWException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationException(FLOWException):
    """Raised when user is not authorized to perform action"""
    
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403)


class UserAlreadyExistsException(FLOWException):
    """Raised when trying to register with existing email/username"""
    
    def __init__(self, message: str = "User already exists"):
        super().__init__(message, status_code=409)


class UserNotFoundException(FLOWException):
    """Raised when user is not found"""
    
    def __init__(self, message: str = "User not found"):
        super().__init__(message, status_code=404)


class InvalidCredentialsException(FLOWException):
    """Raised when credentials are invalid"""
    
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, status_code=401)


class InactiveUserException(FLOWException):
    """Raised when user account is inactive"""
    
    def __init__(self, message: str = "User account is inactive"):
        super().__init__(message, status_code=403)


class InvalidTokenException(FLOWException):
    """Raised when JWT token is invalid or expired"""
    
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, status_code=401)
