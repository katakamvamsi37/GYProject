"""Handle ALB private-IP probes without weakening API host validation."""

from django.http import HttpResponseNotAllowed, JsonResponse


class ContainerHealthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Mounted before SecurityMiddleware only with DJANGO_HTTP_HEALTHCHECK=true.
        # This fixed response reads no host, credentials, user data, or database.
        if request.path_info == "/health/":
            if request.method not in {"GET", "HEAD"}:
                return HttpResponseNotAllowed(["GET", "HEAD"])
            response = JsonResponse({"status": "ok"})
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)
