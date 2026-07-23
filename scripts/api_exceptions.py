"""Custom exception classes for Sarvam AI API error handling.

Provides standardized exception hierarchy for consistent error handling
across all Sarvam AI API calls.

Usage:
    from scripts.api_exceptions import SarvamAPIError, SarvamAuthenticationError
    
    try:
        response = make_api_call()
    except SarvamAuthenticationError:
        print("Invalid API key")
    except SarvamAPIError as e:
        print(f"API error: {e}")
"""


class SarvamAPIError(Exception):
    """Base exception for all Sarvam API errors.
    
    Raised for generic API failures, network errors, and unexpected issues.
    """
    pass


class SarvamAuthenticationError(SarvamAPIError):
    """Raised when API authentication fails.
    
    Occurs when:
    - SARVAM_API_KEY environment variable is missing
    - API key is invalid or expired
    - HTTP 401 response received
    """
    pass


class SarvamRateLimitError(SarvamAPIError):
    """Raised when API rate limit is exceeded.
    
    Occurs when:
    - HTTP 429 (Too Many Requests) response received
    - User has exceeded their quota
    
    Recommendation: Implement exponential backoff retry logic.
    """
    pass


class SarvamValidationError(SarvamAPIError):
    """Raised when API response doesn't match expected structure.
    
    Occurs when:
    - Required fields are missing from response
    - Response cannot be parsed as JSON
    - Response data type is unexpected
    """
    pass


class SarvamServerError(SarvamAPIError):
    """Raised for server-side errors (5xx status codes).
    
    Occurs when:
    - HTTP 500 (Internal Server Error) response received
    - HTTP 502 (Bad Gateway) response received
    - HTTP 503 (Service Unavailable) response received
    
    Recommendation: Implement retry logic with exponential backoff.
    """
    pass


class SarvamTimeoutError(SarvamAPIError):
    """Raised when API request times out.
    
    Occurs when:
    - Request exceeds timeout threshold
    - Network connection is too slow
    
    Recommendation: Increase timeout or implement async processing.
    """
    pass


class SarvamConnectionError(SarvamAPIError):
    """Raised when network connection fails.
    
    Occurs when:
    - Network is unreachable
    - DNS resolution fails
    - Connection refused
    """
    pass
