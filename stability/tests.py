from datetime import date

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.test import Client, TestCase
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Chamber, PlannedSubsample, Product, Sample, SamplingPointTemplate, Study, StudyPlanningEntry
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
        self.chamber = Chamber.objects.create(
            code="CH-001",
            name="Camara 1",
            location="Sala A",
            temperature_set_point=25,
            humidity_set_point=60,
            is_active=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_planning_view_loads_for_study(self):
        response = self.client.get(f"/app/studies/{self.study.id}/planning/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planificacion del estudio")
        self.assertContains(response, self.study.code)

    def test_planning_list_view_loads(self):
        response = self.client.get("/app/planning/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seleccion de estudio")
        self.assertContains(response, self.study.code)

    def test_planning_view_post_saves_entries(self):
        response = self.client.get(f"/app/studies/{self.study.id}/planning/")
        template = SamplingPointTemplate.objects.order_by("month_number").first()

        post_response = self.client.post(
            f"/app/studies/{self.study.id}/planning/",
            data={
                "sampling_point_template": [str(template.id)],
                f"qty_{template.id}_{self.chamber.id}_fq": "3",
                f"qty_{template.id}_{self.chamber.id}_micro": "2",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        entries = StudyPlanningEntry.objects.filter(study=self.study).order_by("analysis_type")
        self.assertEqual(entries.count(), 2)
        self.assertEqual(entries[0].subsample_quantity + entries[1].subsample_quantity, 5)

    def test_generate_planning_creates_planned_subsamples(self):
        template = SamplingPointTemplate.objects.create(month_number=99, label="99M", is_active=True)
        StudyPlanningEntry.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=StudyPlanningEntry.AnalysisType.FQ,
            subsample_quantity=2,
        )
        StudyPlanningEntry.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=StudyPlanningEntry.AnalysisType.MICRO,
            subsample_quantity=1,
        )

        response = self.client.post(
            f"/app/studies/{self.study.id}/planning/",
            data={"action": "generate_planning"},
        )

        self.assertEqual(response.status_code, 302)
        subsamples = PlannedSubsample.objects.filter(study=self.study).order_by("code")
        self.assertEqual(subsamples.count(), 3)
        self.assertEqual(subsamples.first().status, PlannedSubsample.Status.IN_CHAMBER)
        self.assertTrue(subsamples.first().code.startswith(f"{self.study.code}-P-"))

    def test_approving_study_requires_generated_planning(self):
        response = self.client.post(
            f"/app/studies/{self.study.id}/edit/",
            data={
                "code": self.study.code,
                "title": self.study.title,
                "study_type": "",
                "client": "",
                "product": "",
                "product_code": "",
                "protocol": "",
                "specification": "",
                "product_name": self.study.product_name,
                "status": Study.Status.ACTIVE,
                "start_date": str(self.study.start_date),
                "end_date": "",
                "comments": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.study.refresh_from_db()
        self.assertEqual(self.study.status, Study.Status.DRAFT)

    def test_approving_study_calculates_planned_dates(self):
        template = SamplingPointTemplate.objects.create(month_number=3, label="3M", is_active=True)
        StudyPlanningEntry.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=StudyPlanningEntry.AnalysisType.FQ,
            subsample_quantity=1,
        )
        PlannedSubsample.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=PlannedSubsample.AnalysisType.FQ,
            code=f"{self.study.code}-P-0001",
            planned_date=None,
            status=PlannedSubsample.Status.IN_CHAMBER,
        )

        response = self.client.post(
            f"/app/studies/{self.study.id}/edit/",
            data={
                "code": self.study.code,
                "title": self.study.title,
                "study_type": "",
                "client": "",
                "product": "",
                "product_code": "",
                "protocol": "",
                "specification": "",
                "product_name": self.study.product_name,
                "status": Study.Status.ACTIVE,
                "start_date": "2026-07-01",
                "end_date": "",
                "comments": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.study.refresh_from_db()
        self.assertEqual(self.study.status, Study.Status.ACTIVE)
        subsample = PlannedSubsample.objects.get(study=self.study)
        self.assertEqual(str(subsample.planned_date), "2026-10-01")

    def test_withdraw_subsample_requires_approved_study(self):
        template = SamplingPointTemplate.objects.create(month_number=4, label="4M", is_active=True)
        subsample = PlannedSubsample.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=PlannedSubsample.AnalysisType.FQ,
            code=f"{self.study.code}-P-0100",
            status=PlannedSubsample.Status.IN_CHAMBER,
        )

        response = self.client.post(
            f"/app/studies/{self.study.id}/planning/",
            data={"action": "withdraw_subsample", "subsample_id": str(subsample.id)},
        )

        self.assertEqual(response.status_code, 302)
        subsample.refresh_from_db()
        self.assertEqual(subsample.status, PlannedSubsample.Status.IN_CHAMBER)
        self.assertIsNone(subsample.actual_sampling_date)

    def test_withdraw_subsample_sets_real_sampling_date(self):
        self.study.status = Study.Status.ACTIVE
        self.study.save(update_fields=["status", "updated_at"])
        template = SamplingPointTemplate.objects.create(month_number=5, label="5M", is_active=True)
        subsample = PlannedSubsample.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=PlannedSubsample.AnalysisType.MICRO,
            code=f"{self.study.code}-P-0101",
            status=PlannedSubsample.Status.IN_CHAMBER,
        )

        response = self.client.post(
            f"/app/studies/{self.study.id}/planning/",
            data={"action": "withdraw_subsample", "subsample_id": str(subsample.id)},
        )

        self.assertEqual(response.status_code, 302)
        subsample.refresh_from_db()
        self.assertEqual(subsample.status, PlannedSubsample.Status.WITHDRAWN)
        self.assertEqual(str(subsample.actual_sampling_date), str(date.today()))

    def test_edit_generated_subsample_updates_fields(self):
        template = SamplingPointTemplate.objects.create(month_number=7, label="7M", is_active=True)
        subsample = PlannedSubsample.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=PlannedSubsample.AnalysisType.FQ,
            code=f"{self.study.code}-P-0200",
            status=PlannedSubsample.Status.IN_CHAMBER,
        )

        response = self.client.post(
            f"/app/studies/{self.study.id}/planning/",
            data={
                "action": "edit_subsample",
                "subsample_id": str(subsample.id),
                "analysis_date": "2026-07-10",
                "quantity": "4",
                "storage_location": "BALDA A3",
                "location_notes": "Pendiente de verificacion",
            },
        )

        self.assertEqual(response.status_code, 302)
        subsample.refresh_from_db()
        self.assertEqual(str(subsample.analysis_date), "2026-07-10")
        self.assertEqual(subsample.quantity, 4)
        self.assertEqual(subsample.storage_location, "BALDA A3")
        self.assertEqual(subsample.location_notes, "Pendiente de verificacion")

    def test_planned_subsample_label_preview_marks_printed(self):
        template = SamplingPointTemplate.objects.create(month_number=8, label="8M", is_active=True)
        subsample = PlannedSubsample.objects.create(
            study=self.study,
            sampling_point_template=template,
            chamber=self.chamber,
            analysis_type=PlannedSubsample.AnalysisType.MICRO,
            code=f"{self.study.code}-P-0201",
            status=PlannedSubsample.Status.IN_CHAMBER,
        )

        response = self.client.get(f"/app/planned-subsamples/{subsample.id}/label/")

        self.assertEqual(response.status_code, 200)
        subsample.refresh_from_db()
        self.assertIsNotNone(subsample.label_printed_at)


class AdminGroupingTests(TestCase):
    def test_sampling_point_template_is_grouped_under_maestros(self):
        user = User.objects.create_user(
            username="admin.grouping",
            email="admin.grouping@example.com",
            password="Secret123!",
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get("/admin/")
        request.user = user

        app_list = admin.site.get_app_list(request)
        maestros_group = next((app for app in app_list if app.get("app_label") == "maestros"), None)

        self.assertIsNotNone(maestros_group)
        model_names = [model.get("object_name") for model in maestros_group.get("models", [])]
        self.assertIn("SamplingPointTemplate", model_names)
