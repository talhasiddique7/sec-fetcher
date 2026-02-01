class SecFetchError(Exception):
    """Base error for secfetch."""


class MissingUserAgentError(SecFetchError):
    """Raised when SEC user-agent is not provided."""


class RateLimitedError(SecFetchError):
    """Raised when SEC rate limiting is encountered."""


class MasterIndexParseError(SecFetchError):
    """Raised when master.idx cannot be parsed."""

