from django.urls import path

from .views import CurrentUserView, ObtainAccessTokenView, RefreshTokenView, UserCreateView

urlpatterns = [
    path('user/authorization', ObtainAccessTokenView.as_view()),
    path('user/refresh', RefreshTokenView.as_view()),
    path('user', CurrentUserView.as_view()),
    path('user/create', UserCreateView.as_view()),
]
