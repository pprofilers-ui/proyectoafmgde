from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthenticationFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='qa.user',
            email='qa@example.com',
            password='Secret123!',
            company_code='ACME',
        )

    def test_authorization_returns_tokens(self):
        response = self.client.post('/api/user/authorization', {
            'email': 'qa@example.com',
            'password': 'Secret123!',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_me_requires_app_version_header(self):
        token_response = self.client.post('/api/user/authorization', {
            'email': 'qa@example.com',
            'password': 'Secret123!',
        }, format='json')
        token = token_response.data['access']

        response = self.client.get('/api/user', HTTP_AUTHORIZATION=f'Bearer {token}')

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
