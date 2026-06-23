from django import forms

from .models import (
    Chamber,
    ChamberDeviation,
    LabelTemplate,
    PackagingConfiguration,
    Sample,
    SampleSchedule,
    SampleReception,
    SamplingPoint,
    Study,
)


def _apply_bootstrap(field, placeholder=None):
    widget = field.widget
    existing = widget.attrs.get("class", "")
    if isinstance(widget, forms.CheckboxInput):
        widget.attrs["class"] = f"{existing} form-check-input".strip()
        return
    css_class = "form-control"
    if isinstance(widget, (forms.Select,)):
        css_class = "form-select"
    if isinstance(widget, (forms.Textarea,)):
        css_class = "form-control"
    widget.attrs["class"] = f"{existing} {css_class} rounded-4 shadow-sm".strip()
    if placeholder:
        widget.attrs["placeholder"] = placeholder


class SampleReceptionForm(forms.ModelForm):
    class Meta:
        model = SampleReception
        fields = [
            "study",
            "batch",
            "reception_number",
            "received_from",
            "received_by",
            "received_at",
            "quantity_received",
            "quantity_expected",
            "discrepancy_notes",
            "quantity_assigned",
            "quantity_reserved",
            "quantity_contingency",
            "status",
            "notes",
        ]
        widgets = {
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "discrepancy_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study"].queryset = Study.objects.order_by("code")
        self.fields["batch"].required = False
        self.fields["received_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        labels = {
            "study": "Estudio",
            "batch": "Lote",
            "reception_number": "Numero de recepcion",
            "received_from": "Recibido desde",
            "received_by": "Recibido por",
            "received_at": "Fecha y hora de recepcion",
            "quantity_received": "Cantidad recibida",
            "quantity_expected": "Cantidad prevista",
            "discrepancy_notes": "Discrepancias detectadas",
            "quantity_assigned": "Cantidad asignada",
            "quantity_reserved": "Cantidad reservada",
            "quantity_contingency": "Cantidad de contingencia",
            "status": "Estado",
            "notes": "Notas",
        }
        placeholders = {
            "reception_number": "Ej. REC-2026-001",
            "received_from": "Origen de la muestra",
            "received_by": "Usuario o tecnico receptor",
            "quantity_received": "Cantidad recibida",
            "quantity_expected": "Cantidad prevista en protocolo",
            "quantity_assigned": "Cantidad asignada a condiciones",
            "quantity_reserved": "Cantidad reservada",
            "quantity_contingency": "Cantidad extra o contingencia",
            "notes": "Observaciones de recepcion",
            "discrepancy_notes": "Describe cualquier discrepancia detectada",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))


class StudyCreateForm(forms.ModelForm):
    class Meta:
        model = Study
        fields = [
            "code",
            "title",
            "packaging",
            "product_name",
            "batch_number",
            "packaging_description",
            "status",
            "start_date",
            "end_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["packaging"].queryset = PackagingConfiguration.objects.filter(is_active=True).order_by("code")
        labels = {
            "code": "Codigo",
            "title": "Titulo",
            "packaging": "Acondicionado",
            "product_name": "Nombre del producto",
            "batch_number": "Numero de lote",
            "packaging_description": "Comentarios",
            "status": "Estado",
            "start_date": "Fecha de inicio",
            "end_date": "Fecha de fin",
        }
        placeholders = {
            "code": "Ej. EST-2026-003",
            "title": "Titulo del estudio",
            "product_name": "Nombre visible del producto",
            "batch_number": "Codigo del lote",
            "packaging_description": "Comentarios",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["code"].required = False
        self.fields["code"].widget.attrs["readonly"] = True
        self.fields["code"].widget.attrs["tabindex"] = "-1"
        self.fields["packaging"].required = False
        self.fields["end_date"].required = False


class StudyEditForm(forms.ModelForm):
    class Meta:
        model = Study
        fields = [
            "code",
            "title",
            "packaging",
            "product_name",
            "batch_number",
            "packaging_description",
            "status",
            "start_date",
            "end_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["packaging"].queryset = PackagingConfiguration.objects.filter(is_active=True).order_by("code")
        labels = {
            "code": "Codigo",
            "title": "Titulo",
            "packaging": "Acondicionado",
            "product_name": "Nombre del producto",
            "batch_number": "Numero de lote",
            "packaging_description": "Comentarios",
            "status": "Estado",
            "start_date": "Fecha de inicio",
            "end_date": "Fecha de fin",
        }
        placeholders = {
            "code": "Ej. EST-2026-003",
            "title": "Titulo del estudio",
            "product_name": "Nombre visible del producto",
            "batch_number": "Codigo del lote",
            "packaging_description": "Comentarios",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["code"].required = False
        self.fields["code"].widget.attrs["readonly"] = True
        self.fields["code"].widget.attrs["tabindex"] = "-1"
        self.fields["packaging"].required = False
        self.fields["end_date"].required = False


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
        fields = ["planned_date", "label", "notes", "is_active"]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.TextInput(),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "planned_date": "Fecha de muestreo",
            "label": "Etiqueta",
            "notes": "Notas",
            "is_active": "Activa",
        }
        placeholders = {
            "label": "Ej. T0, T1, T2, T3",
            "notes": "Observaciones opcionales",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))


class SampleScheduleEditForm(forms.ModelForm):
    class Meta:
        model = SampleSchedule
        fields = ["planned_date", "label", "notes", "is_active"]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.TextInput(),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "planned_date": "Fecha de muestreo",
            "label": "Etiqueta",
            "notes": "Notas",
            "is_active": "Activa",
        }
        placeholders = {
            "label": "Ej. T0, T1, T2, T3",
            "notes": "Observaciones opcionales",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))


class ChamberDeviationForm(forms.ModelForm):
    class Meta:
        model = ChamberDeviation
        fields = [
            "chamber",
            "study",
            "detected_at",
            "description",
            "impact_assessment",
            "requires_recalculation",
        ]
        widgets = {
            "detected_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "impact_assessment": forms.Textarea(attrs={"rows": 3}),
            "requires_recalculation": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["chamber"].queryset = Chamber.objects.filter(is_active=True).order_by("code")
        self.fields["study"].queryset = Study.objects.order_by("code")
        self.fields["study"].required = False
        self.fields["detected_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        labels = {
            "chamber": "Camara",
            "study": "Estudio",
            "detected_at": "Fecha y hora de deteccion",
            "description": "Descripcion",
            "impact_assessment": "Evaluacion de impacto",
            "requires_recalculation": "Requiere recalculo de fechas",
        }
        placeholders = {
            "description": "Describe la desviacion detectada en la camara",
            "impact_assessment": "Indica el impacto y las acciones tomadas",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            _apply_bootstrap(field, placeholders.get(name))
        self.fields["requires_recalculation"].help_text = "Marca esta opcion solo si quieres recalcular las fechas de muestreo del estudio asociado."
