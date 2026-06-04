class InvalidAccountIdentity(Exception):
    """Raised when a Django user has an invalid business identity."""


class AccountCreationError(ValueError):
    """Raised when an account cannot be created."""
