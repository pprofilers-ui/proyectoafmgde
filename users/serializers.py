from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'company_code',
            'contact_code', 'address_code', 'user_type', 'is_quality_admin',
        )


class ObtainAccessTokenSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD

    def validate(self, attrs):
        credentials = {
            'email': attrs.get('email', '').lower(),
            'password': attrs.get('password'),
        }
        user = User.objects.filter(email=credentials['email']).first()
        if user is None or not user.check_password(credentials['password']):
            raise serializers.ValidationError({'errors': [{'code': 'invalid_credentials', 'detail': 'Invalid email or password.'}]})

        refresh = self.get_token(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['company_code'] = user.company_code
        token['contact_code'] = user.contact_code
        token['user_type'] = user.user_type
        return token


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'username', 'email', 'password', 'first_name', 'last_name', 'company_code',
            'contact_code', 'address_code', 'user_type', 'is_quality_admin',
        )

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.email = user.email.lower()
        user.set_password(password)
        user.save()
        return user
