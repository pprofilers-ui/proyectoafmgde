from django import forms
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Chamber,
    ChamberDeviation,
    ChamberLocation,
    Client,
    LabelTemplate,
    PackagingConfiguration,
    Product,
    ProductBatch,
    Sample,
    SampleSchedule,
    SampleReception,
    SamplingPoint,
    Study,
    StudyType,
)


def _apply_bootstrap(field, placeholder=None):
    widget = field.widget
    existing = widget.attrs.get("class", "")

    if isinstance(widget, forms.CheckboxInput):
        widget.attrs["class"] = f"{existing} form-check-input".strip()
        return

    css_class = "form-control"

    if isinstance(widget, forms.Select):
        css_class = "form-select"

    widget.attrs["class"] = f"{existing} {css_class} rounded-4 shadow-sm".strip()

    if placeholder:
        widget.attrs["placeholder"] = placeholder


def _chamber_key_from_code(code):
    cleaned = (code or "").strip().upper().replace("-", "")
    return cleaned


def _location_matches_chamber(chamber, chamber_location):
    if not chamber or not chamber_location:
        return True
    chamber_key = _chamber_key_from_code(getattr(chamber, "code", ""))
    location_code = (getattr(chamber_location, "code", "") or "").strip().upper()
    return location_code.startswith(f"{chamber_key}-")


def _validate_assigned_quantity_limit(form, cleaned_data, sample, current_instance=None):
    if not sample or not getattr(sample, "reception", None):
        return

    received_quantity = sample.reception.quantity_received or 0
    current_quantity = cleaned_data.get("quantity") or 0
    is_active = cleaned_data.get("is_active")

    active_schedules = sample.schedules.filter(is_active=True)
    if current_instance and current_instance.pk:
        active_schedules = active_schedules.exclude(pk=current_instance.pk)

    already_assigned = active_schedules.aggregate(total=Sum("quantity")).get("total") or 0
    new_total = already_assigned + (current_quantity if is_active else 0)

    if new_total > received_quantity:
        form.add_error(
            "quantity",
            f"La cantidad asignada total seria {new_total} y no puede superar la cantidad recibida ({received_quantity}).",
        )


def _next_reception_number():
    from .models import SampleReception

    year = timezone.localdate().year
    prefix = f"REC-{year}-"

    existing = SampleReception.objects.filter(
        reception_number__startswith=prefix
    ).values_list(
        "reception_number",
        flat=True,
    )

    max_seq = 0

    for value in existing:
        suffix = value.replace(prefix, "")
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    return f"{prefix}{max_seq + 1:03d}"


class SampleReceptionForm(forms.ModelForm):
    batch = forms.CharField(label="Lote", required=False)

    class Meta:
        model = SampleReception
        fields = [
            "study",
            "reception_number",
            "presentation",
            "packaging",
            "batch",
            "batch_size",
            "bulk_code",
            "api_batch",
            "api_code",
            "primary_packing_material",
            "manufacture_date",
            "received_by",
            "received_at",
            "quantity_received",
            "quantity_expected",
            "quantity_assigned",
            "quantity_reserved",
            "quantity_contingency",
            "notes",
        ]
        widgets = {
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "manufacture_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study"].queryset = Study.objects.order_by("code")
        self.fields["packaging"].queryset = PackagingConfiguration.objects.filter(is_active=True).order_by("code")
        self.fields["received_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        labels = {
            "study": "Estudio",
            "presentation": "Presentacion",
            "packaging": "Formato",
            "batch": "Lote",
            "batch_size": "Batch Size",
            "bulk_code": "Code Bulk",
            "api_batch": "API Batch",
            "api_code": "API Code",
            "primary_packing_material": "Primary Packing Material",
            "manufacture_date": "Manufacture Date",
            "reception_number": "Numero de recepcion",
            "received_by": "Recibido por",
            "received_at": "Fecha y hora de recepcion",
            "quantity_received": "Cantidad recibida",
            "quantity_expected": "Cantidad prevista",
            "quantity_assigned": "Cantidad asignada",
            "quantity_reserved": "Cantidad reservada",
            "quantity_contingency": "Cantidad de contingencia",
            "notes": "Observaciones",
        }
        placeholders = {
            "presentation": "Presentacion del producto",
            "received_by": "Usuario o tecnico receptor",
            "batch_size": "Tamano del batch",
            "bulk_code": "Codigo bulk",
            "api_batch": "Lote API",
            "api_code": "Codigo API",
            "primary_packing_material": "Material de acondicionamiento primario",
            "quantity_received": "Cantidad recibida",
            "quantity_expected": "Cantidad prevista en protocolo",
            "quantity_assigned": "Cantidad asignada a condiciones",
            "quantity_reserved": "Cantidad reservada",
            "quantity_contingency": "Cantidad extra o contingencia",
            "notes": "Observaciones de recepcion",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        if self.instance and self.instance.pk and self.instance.batch:
            self.fields["batch"].initial = self.instance.batch.code
        elif self.instance and self.instance.pk and self.instance.batch_number_text:
            self.fields["batch"].initial = self.instance.batch_number_text
        self.fields["batch"].widget.attrs["placeholder"] = "Ej. LOT-328"

    def save(self, commit=True):
        instance = super().save(commit=False)
        batch_code = (self.cleaned_data.get("batch") or "").strip()
        instance.batch_number_text = batch_code
        if batch_code:
            instance.batch = ProductBatch.objects.filter(code=batch_code).first()
        else:
            instance.batch = None
        if commit:
            instance.save()
        return instance


class StudyCreateForm(forms.ModelForm):
    class Meta:
        model = Study
        fields = [
            "code",
            "title",
            "study_type",
            "client",
            "product",
            "product_code",
            "protocol",
            "specification",
            "product_name",
            "status",
            "start_date",
            "end_date",
            "comments",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "comments": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study_type"].queryset = StudyType.objects.filter(is_active=True).order_by("name")
        self.fields["client"].queryset = Client.objects.order_by("code")
        self.fields["product"].queryset = Product.objects.filter(is_active=True).order_by("code")
        labels = {
            "code": "Codigo",
            "title": "Titulo",
            "study_type": "Tipo de estudio",
            "client": "Cliente",
            "product": "Producto",
            "product_code": "Codigo Producto",
            "protocol": "Protocolo",
            "specification": "Especificacion",
            "product_name": "Nombre del producto",
            "status": "Estado",
            "start_date": "Fecha de inicio",
            "end_date": "Fecha de fin",
            "comments": "Comentarios",
        }
        placeholders = {
            "code": "Ej. EST-2026-003",
            "title": "Titulo del estudio",
            "study_type": "Selecciona el tipo de estudio",
            "client": "Cliente del estudio",
            "product_code": "Codigo interno del producto",
            "protocol": "Codigo de protocolo",
            "specification": "Referencia de especificacion",
            "product_name": "Nombre visible del producto",
            "comments": "Comentarios",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["code"].required = False
        self.fields["code"].widget.attrs["readonly"] = True
        self.fields["code"].widget.attrs["tabindex"] = "-1"
        self.fields["end_date"].required = False

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if status == Study.Status.ACTIVE and not start_date:
            self.add_error("start_date", "La fecha de inicio es obligatoria cuando el estudio esta aprobado.")

        if status == Study.Status.CLOSED and not end_date:
            self.add_error("end_date", "La fecha de fin es obligatoria cuando el estudio esta finalizado.")

        return cleaned_data


class StudyEditForm(forms.ModelForm):
    class Meta:
        model = Study
        fields = [
            "code",
            "title",
            "study_type",
            "client",
            "product",
            "product_code",
            "protocol",
            "specification",
            "product_name",
            "status",
            "start_date",
            "end_date",
            "comments",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "comments": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study_type"].queryset = StudyType.objects.filter(is_active=True).order_by("name")
        self.fields["client"].queryset = Client.objects.order_by("code")
        self.fields["product"].queryset = Product.objects.filter(is_active=True).order_by("code")
        labels = {
            "code": "Codigo",
            "title": "Titulo",
            "study_type": "Tipo de estudio",
            "client": "Cliente",
            "product": "Producto",
            "product_code": "Codigo Producto",
            "protocol": "Protocolo",
            "specification": "Especificacion",
            "product_name": "Nombre del producto",
            "status": "Estado",
            "start_date": "Fecha de inicio",
            "end_date": "Fecha de fin",
            "comments": "Comentarios",
        }
        placeholders = {
            "code": "Ej. EST-2026-003",
            "title": "Titulo del estudio",
            "study_type": "Selecciona el tipo de estudio",
            "client": "Cliente del estudio",
            "product_code": "Codigo interno del producto",
            "protocol": "Codigo de protocolo",
            "specification": "Referencia de especificacion",
            "product_name": "Nombre visible del producto",
            "comments": "Comentarios",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["code"].required = False
        self.fields["code"].widget.attrs["readonly"] = True
        self.fields["code"].widget.attrs["tabindex"] = "-1"
        self.fields["end_date"].required = False

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if status == Study.Status.ACTIVE and not start_date:
            self.add_error("start_date", "La fecha de inicio es obligatoria cuando el estudio esta aprobado.")

        if status == Study.Status.CLOSED and not end_date:
            self.add_error("end_date", "La fecha de fin es obligatoria cuando el estudio esta finalizado.")

        return cleaned_data


class SampleLabelForm(forms.Form):
    sample = forms.ModelChoiceField(queryset=Sample.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sample"].queryset = Sample.objects.order_by("sample_code")
        self.fields["sample"].label = "Muestra"
        _apply_bootstrap(self.fields["sample"])


class SampleCreateForm(forms.ModelForm):
    class Meta:
        model = Sample
        fields = [
            "study",
            "reception",
            "label_template",
            "sample_code",
            "quantity",
            "current_stock",
            "status",
            "shelf",
            "tray",
            "container",
            "physical_position",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study"].queryset = Study.objects.order_by("code")
        self.fields["reception"].queryset = SampleReception.objects.order_by("-received_at")
        self.fields["label_template"].queryset = LabelTemplate.objects.filter(is_active=True).order_by("code")
        labels = {
            "study": "Estudio",
            "reception": "Recepcion",
            "label_template": "Plantilla de etiqueta",
            "sample_code": "Codigo de muestra",
            "quantity": "Cantidad total",
            "current_stock": "Stock inicial",
            "status": "Estado",
            "shelf": "Estanteria",
            "tray": "Bandeja",
            "container": "Contenedor",
            "physical_position": "Posicion",
        }
        placeholders = {
            "sample_code": "Ej. EST-2026-003-M-001",
            "quantity": "Cantidad total",
            "current_stock": "Stock inicial",
            "shelf": "Estanteria",
            "tray": "Bandeja",
            "container": "Caja o contenedor",
            "physical_position": "Posicion",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["sample_code"].required = False
        self.fields["sample_code"].widget.attrs["readonly"] = True
        self.fields["sample_code"].widget.attrs["tabindex"] = "-1"
        self.fields["reception"].required = False


class SampleRegistrationForm(forms.Form):
    study = forms.ModelChoiceField(queryset=Study.objects.none())
    presentation = forms.CharField(required=False)
    packaging = forms.ModelChoiceField(queryset=PackagingConfiguration.objects.none(), required=False)
    batch = forms.CharField(required=False)
    batch_size = forms.IntegerField(min_value=0, initial=0, required=False)
    bulk_code = forms.CharField(required=False)
    api_batch = forms.CharField(required=False)
    api_code = forms.CharField(required=False)
    primary_packing_material = forms.CharField(required=False)
    manufacture_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    reception_number = forms.CharField(max_length=50)
    received_by = forms.CharField(max_length=255, required=False)
    received_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    quantity_received = forms.IntegerField(min_value=0, initial=1)
    quantity_expected = forms.IntegerField(min_value=0, initial=1)
    quantity_assigned = forms.IntegerField(min_value=0, initial=0)
    quantity_reserved = forms.IntegerField(min_value=0, initial=0)
    quantity_contingency = forms.IntegerField(min_value=0, initial=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study"].queryset = Study.objects.order_by("code")
        self.fields["packaging"].queryset = PackagingConfiguration.objects.filter(is_active=True).order_by("code")
        self.fields["received_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        labels = {
            "study": "Estudio",
            "presentation": "Presentacion",
            "packaging": "Formato",
            "batch": "Lote",
            "batch_size": "Batch Size",
            "bulk_code": "Code Bulk",
            "api_batch": "API Batch",
            "api_code": "API Code",
            "primary_packing_material": "Primary Packing Material",
            "manufacture_date": "Manufacture Date",
            "reception_number": "Numero de recepcion",
            "received_by": "Recibido por",
            "received_at": "Fecha y hora de recepcion",
            "quantity_received": "Cantidad recibida",
            "quantity_expected": "Cantidad prevista",
            "quantity_assigned": "Cantidad asignada",
            "quantity_reserved": "Cantidad reservada",
            "quantity_contingency": "Cantidad de contingencia",
            "notes": "Observaciones",
        }
        placeholders = {
            "presentation": "Presentacion del producto",
            "batch": "Ej. LOT-328",
            "batch_size": "Tamano del batch",
            "bulk_code": "Codigo bulk",
            "api_batch": "Lote API",
            "api_code": "Codigo API",
            "primary_packing_material": "Material de acondicionamiento primario",
            "reception_number": "Ej. REC-2026-001",
            "received_by": "Usuario o tecnico receptor",
            "quantity_received": "Cantidad recibida",
            "quantity_expected": "Cantidad prevista en protocolo",
            "quantity_assigned": "Cantidad asignada a condiciones",
            "quantity_reserved": "Cantidad reservada",
            "quantity_contingency": "Cantidad extra o contingencia",
            "notes": "Observaciones de recepcion",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["reception_number"].initial = _next_reception_number()
        self.fields["reception_number"].widget.attrs["readonly"] = True
        self.fields["quantity_assigned"].widget.attrs["readonly"] = True


class ChamberPlacementForm(forms.Form):
    sample = forms.ModelChoiceField(queryset=Sample.objects.none())
    chamber = forms.ModelChoiceField(queryset=Chamber.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sample"].queryset = Sample.objects.order_by("sample_code")
        self.fields["chamber"].queryset = Chamber.objects.filter(is_active=True).order_by("code")
        self.fields["sample"].label = "Muestra"
        self.fields["chamber"].label = "Camara"
        _apply_bootstrap(self.fields["sample"])
        _apply_bootstrap(self.fields["chamber"])


class SampleExtractionForm(forms.Form):
    sample = forms.ModelChoiceField(queryset=Sample.objects.none())
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sample"].queryset = Sample.objects.order_by("sample_code")
        self.fields["sample"].label = "Muestra"
        self.fields["quantity"].label = "Cantidad"
        _apply_bootstrap(self.fields["sample"])
        _apply_bootstrap(self.fields["quantity"], "Cantidad a extraer")


class SampleScheduleForm(forms.ModelForm):
    class Meta:
        model = SampleSchedule
        fields = ["planned_date", "chamber", "chamber_location", "quantity", "notes", "is_active"]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.TextInput(),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        self.sample = kwargs.pop("sample", None)
        super().__init__(*args, **kwargs)
        self.fields["chamber"].queryset = Chamber.objects.filter(is_active=True).order_by("code")
        self.fields["chamber_location"].queryset = ChamberLocation.objects.filter(is_active=True).order_by("code")
        self.fields["chamber"].required = False
        self.fields["chamber_location"].required = False
        labels = {
            "planned_date": "Fecha de muestreo",
            "label": "Código fecha de muestreo",
            "chamber": "Camara",
            "chamber_location": "Ubicacion",
            "quantity": "Cantidad",
            "notes": "Notas",
            "is_active": "Activa",
        }
        placeholders = {
            "label": "Generado automáticamente",
            "notes": "Observaciones opcionales",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))

    def clean(self):
        cleaned_data = super().clean()
        chamber = cleaned_data.get("chamber")
        chamber_location = cleaned_data.get("chamber_location")
        if chamber and chamber_location and not _location_matches_chamber(chamber, chamber_location):
            self.add_error("chamber_location", "La ubicacion seleccionada no pertenece a la camara indicada.")
        _validate_assigned_quantity_limit(self, cleaned_data, self.sample)
        return cleaned_data


class SampleScheduleEditForm(forms.ModelForm):
    class Meta:
        model = SampleSchedule
        fields = ["planned_date", "chamber", "chamber_location", "quantity", "notes", "is_active"]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.TextInput(),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["chamber"].queryset = Chamber.objects.filter(is_active=True).order_by("code")
        self.fields["chamber_location"].queryset = ChamberLocation.objects.filter(is_active=True).order_by("code")
        self.fields["chamber"].required = False
        self.fields["chamber_location"].required = False
        labels = {
            "planned_date": "Fecha de muestreo",
            "label": "Código fecha de muestreo",
            "chamber": "Camara",
            "chamber_location": "Ubicacion",
            "quantity": "Cantidad",
            "notes": "Notas",
            "is_active": "Activa",
        }
        placeholders = {
            "label": "Generado automáticamente",
            "notes": "Observaciones opcionales",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))

    def clean(self):
        cleaned_data = super().clean()
        chamber = cleaned_data.get("chamber")
        chamber_location = cleaned_data.get("chamber_location")
        if chamber and chamber_location and not _location_matches_chamber(chamber, chamber_location):
            self.add_error("chamber_location", "La ubicacion seleccionada no pertenece a la camara indicada.")
        _validate_assigned_quantity_limit(self, cleaned_data, getattr(self.instance, "sample", None), self.instance)
        return cleaned_data


class ChamberDeviationForm(forms.ModelForm):
    class Meta:
        model = ChamberDeviation
        fields = [
            "deviation_code",
            "chamber",
            "detected_at",
            "ended_at",
            "description",
            "impact_assessment",
            "requires_recalculation",
        ]
        widgets = {
            "detected_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ended_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "impact_assessment": forms.Textarea(attrs={"rows": 3}),
            "requires_recalculation": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["chamber"].queryset = Chamber.objects.filter(is_active=True).order_by("code")
        self.fields["detected_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ended_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["deviation_code"].required = False
        self.fields["deviation_code"].widget.attrs["readonly"] = True
        self.fields["deviation_code"].widget.attrs["tabindex"] = "-1"
        labels = {
            "deviation_code": "Codigo Desviacion",
            "chamber": "Camara",
            "detected_at": "Fecha y hora de inicio",
            "ended_at": "Fecha y hora de fin",
            "description": "Descripcion",
            "impact_assessment": "Evaluacion de impacto",
            "requires_recalculation": "Requiere recalculo de fechas",
        }
        placeholders = {
            "deviation_code": "Se generara automaticamente",
            "description": "Describe la desviacion detectada en la camara",
            "impact_assessment": "Indica el impacto y las acciones tomadas",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["requires_recalculation"].help_text = "Marca esta opcion solo si quieres recalcular las fechas de todas las muestras activas de esta camara."
