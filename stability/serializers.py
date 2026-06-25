from rest_framework import serializers

from .models import (
    Chamber,
    ChamberDeviation,
    ChamberLocation,
    PackagingConfiguration,
    Product,
    ProductBatch,
    Sample,
    SampleReception,
    SamplingPoint,
    StabilityAlert,
    StockMovement,
    StorageCondition,
    Study,
    StudyType,
)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class PackagingConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagingConfiguration
        fields = "__all__"


class ProductBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductBatch
        fields = "__all__"


class StorageConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageCondition
        fields = "__all__"


class ChamberLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChamberLocation
        fields = "__all__"


class StudySerializer(serializers.ModelSerializer):
    class Meta:
        model = Study
        fields = "__all__"


class StudyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyType
        fields = "__all__"


class ChamberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chamber
        fields = "__all__"


class SamplingPointSerializer(serializers.ModelSerializer):
    effective_date = serializers.DateField(read_only=True)

    class Meta:
        model = SamplingPoint
        fields = "__all__"


class SampleReceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SampleReception
        fields = "__all__"


class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = "__all__"


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = "__all__"


class ChamberDeviationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChamberDeviation
        fields = "__all__"


class StabilityAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = StabilityAlert
        fields = "__all__"
