from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, NotAcceptable
from rest_framework_simplejwt.authentication import JWTAuthentication


class ContextJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        app_version = request.headers.get('app-version')
        if app_version is None:
            raise NotAcceptable('Should pass app-version in request headers.')
        if app_version != settings.REQUIRED_APP_VERSION:
            raise NotAcceptable(f'Should use app-version: {settings.REQUIRED_APP_VERSION}.')

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        request.company_code = request.headers.get('company') or user.company_code
        request.contact_code = request.headers.get('contact') or user.contact_code
        request.address_code = request.headers.get('address') or user.address_code
        request.lang_code = request.headers.get('lang', 'es')

        if not request.company_code and user.user_type != user.UserType.INTERNAL:
            raise AuthenticationFailed('Company context is required for client users.')

        return user, validated_token
