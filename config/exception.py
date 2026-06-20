from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import set_rollback


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        if isinstance(exc.detail, (list, dict)):
            data = exc.detail
        elif isinstance(exc, exceptions.NotAuthenticated):
            data = {'errors': [{'code': 'not_authenticated', 'detail': 'Authentication credentials were not provided.'}]}
        elif isinstance(exc, exceptions.AuthenticationFailed):
            data = {'errors': [{'code': 'authentication_failed', 'detail': str(exc.detail)}]}
        elif isinstance(exc, exceptions.PermissionDenied):
            data = {'errors': [{'code': 'permission_denied', 'detail': str(exc.detail)}]}
        else:
            data = {'errors': [{'code': 'api_error', 'detail': str(exc.detail)}]}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    return None
