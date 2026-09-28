class DomainError(Exception):
    """Base class for all business-rule violations in the application."""


class AuthenticationError(DomainError):
    """Raised when login credentials are invalid."""


class AccountBlockedError(DomainError):
    """Raised when a blocked account attempts to authenticate."""


class AuthorizationError(DomainError):
    """Raised when a user attempts an action their role does not permit."""


class EntityNotFoundError(DomainError):
    """Raised when a requested entity does not exist in its repository."""


class DuplicateLoginError(DomainError):
    """Raised when a new account is registered with a login already in use."""


class UnsupportedFileTypeError(DomainError):
    """Raised when an uploaded file's extension is not in the allowed list."""


class FileTooLargeError(DomainError):
    """Raised when an uploaded file exceeds the maximum allowed size."""


class SourceFileNotFoundError(DomainError):
    """Raised when the local file path given for an upload does not exist."""


class ValidationError(DomainError):
    """Raised when required input fields are missing or malformed."""
