from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Product, Sample, Study
from .web_forms import StudyCreateForm, StudyEditForm


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


class StudyFormValidationTests(TestCase):
    def test_create_form_requires_end_date_when_study_is_closed(self):
        form = StudyCreateForm(
            data={
                "title": "Estudio finalizado",
                "product_name": "Producto test",
                "status": Study.Status.CLOSED,
                "start_date": str(date.today()),
                "end_date": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_edit_form_accepts_approved_study_with_start_date(self):
        study = Study.objects.create(
            code="EST-VAL-001",
            title="Estudio aprobado",
            product_name="Producto test",
            batch_number="L-001",
            company_code="ACME",
            status=Study.Status.DRAFT,
            start_date=date.today(),
        )

        form = StudyEditForm(
            data={
                "code": study.code,
                "title": study.title,
                "study_type": "",
                "client": "",
                "product": "",
                "product_code": "",
                "protocol": "",
                "specification": "",
                "product_name": study.product_name,
                "status": Study.Status.ACTIVE,
                "start_date": str(date.today()),
                "end_date": "",
                "comments": "",
            },
            instance=study,
        )

        self.assertTrue(form.is_valid(), form.errors)


class PlanningViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="planner.user",
            email="planner@example.com",
            password="Secret123!",
        )
        self.study = Study.objects.create(
            code="EST-PLAN-001",
            title="Estudio planificacion",
            product_name="Producto test",
            batch_number="L-PLAN-001",
            company_code="ACME",
            start_date=date.today(),
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_planning_view_loads_for_study(self):
        response = self.client.get(f"/app/studies/{self.study.id}/planning/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planificacion del estudio")
        self.assertContains(response, self.study.code)
