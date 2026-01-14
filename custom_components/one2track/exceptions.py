"""Exceptions for One2Track integration."""


class One2TrackError(Exception):
    """Base exception for One2Track integration."""


class One2TrackAuthenticationError(One2TrackError):
    """Exception raised for authentication failures."""


class One2TrackConnectionError(One2TrackError):
    """Exception raised for connection failures."""


class One2TrackApiError(One2TrackError):
    """Exception raised for API errors."""
