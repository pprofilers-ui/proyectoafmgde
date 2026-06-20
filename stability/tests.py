from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Product, Sample, Study


User = get_user_model()


class StudyApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="study.user",
            email="study@example.com",
            password="Secret123!",
            company_code="ACME",
        )
        self.product = Product.objects.create(
            code="PROD-TEST",
            name="Producto test",
            company_code="ACME",
        )
        token = RefreshToken.for_user(self.user)
        self.auth_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token.access_token}",
            "HTTP_APP_VERSION": "1.0.0",
            "HTTP_COMPANY": "ACME",
        }

    def test_create_study_uses_request_company_scope(self):
        payload = {
            "code": "EST-001",
            "title": "Estudio inicial",
            "product": self.product.id,
            "product_name": "Producto test",
            "batch_number": "L-100",
            "packaging_description": "Blister",
            "company_code": "OTHER",
            "status": "draft",
            "start_date": str(date.today()),
        }

        response = self.client.post("/api/stability/studies/", payload, format="json", **self.auth_headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["company_code"], "ACME")

    def test_stock_summary_endpoint_works(self):
        study = Study.objects.create(
            code="EST-002",
            title="Estudio stock",
            product=self.product,
            product_name="Producto test",
            batch_number="L-200",
            company_code="ACME",
            start_date=date.today(),
        )
        Sample.objects.create(
            study=study,
            sample_code="SAMPLE-001",
            quantity=5,
            current_stock=2,
            status=Sample.Status.LABELLED,
        )

        response = self.client.get("/api/stability/samples/stock-summary/", **self.auth_headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("by_status", response.data)
        self.assertEqual(response.data["low_stock_samples"], 1)
