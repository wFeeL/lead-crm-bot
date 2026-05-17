class AppError(Exception):
    """Base expected application error."""


class NotFoundError(AppError):
    pass


class PermissionDeniedError(AppError):
    pass


class InvalidStatusTransitionError(AppError):
    pass


class RateLimitExceededError(AppError):
    pass


class ValidationError(AppError):
    pass
