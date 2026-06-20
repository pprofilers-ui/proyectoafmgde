from threading import local


_audit_local = local()


def set_audit_request(request):
    _audit_local.request = request


def get_audit_request():
    return getattr(_audit_local, "request", None)


def clear_audit_request():
    if hasattr(_audit_local, "request"):
        delattr(_audit_local, "request")
