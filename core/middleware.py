class SecurityHeadersMiddleware:
    """Set a small same-origin policy for the first-party HTML app."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; "
            "script-src 'self'; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none';",
        )
        return response
