from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import ObtainAccessTokenSerializer, UserCreateSerializer, UserSerializer


class ObtainAccessTokenView(TokenObtainPairView):
    serializer_class = ObtainAccessTokenSerializer

    @swagger_auto_schema(
        operation_description='Autentica al usuario y devuelve access/refresh token con contexto corporativo.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'password'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'password': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        tags=['Authorization'],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RefreshTokenView(TokenRefreshView):
    @swagger_auto_schema(operation_description='Renueva el access token a partir del refresh token.', tags=['Authorization'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    @swagger_auto_schema(tags=['User'])
    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(request.user).data)

    def get_object(self):
        return self.request.user


class UserCreateView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(tags=['User'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
