from .context import clear_audit_request, set_audit_request


class AuditRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        company_code = ""
        contact_code = ""
        if user is not None and getattr(user, "is_authenticated", False):
            company_code = getattr(user, "company_code", "") or "AGQ"
            contact_code = getattr(user, "contact_code", "") or ""
        request.company_code = company_code
        request.contact_code = contact_code
        set_audit_request(request)
        try:
            response = self.get_response(request)
        finally:
            clear_audit_request()
        return response
