from rest_framework.routers import DefaultRouter

from .views import (
    ChamberDeviationViewSet,
    ChamberLocationViewSet,
    ChamberViewSet,
    PackagingConfigurationViewSet,
    ProductBatchViewSet,
    ProductViewSet,
    SampleReceptionViewSet,
    SampleViewSet,
    SamplingPointViewSet,
    StabilityAlertViewSet,
    StockMovementViewSet,
    StorageConditionViewSet,
    StudyViewSet,
    StudyTypeViewSet,
)

router = DefaultRouter()
router.register(r"stability/products", ProductViewSet, basename="stability-product")
router.register(r"stability/packaging", PackagingConfigurationViewSet, basename="stability-packaging")
router.register(r"stability/batches", ProductBatchViewSet, basename="stability-batch")
router.register(r"stability/storage-conditions", StorageConditionViewSet, basename="stability-storage-condition")
router.register(r"stability/chamber-locations", ChamberLocationViewSet, basename="stability-chamber-location")
router.register(r"stability/study-types", StudyTypeViewSet, basename="stability-study-type")
router.register(r"stability/studies", StudyViewSet, basename="stability-study")
router.register(r"stability/chambers", ChamberViewSet, basename="stability-chamber")
router.register(r"stability/sampling-points", SamplingPointViewSet, basename="stability-sampling-point")
router.register(r"stability/receptions", SampleReceptionViewSet, basename="stability-reception")
router.register(r"stability/samples", SampleViewSet, basename="stability-sample")
router.register(r"stability/stock-movements", StockMovementViewSet, basename="stability-stock-movement")
router.register(r"stability/chamber-deviations", ChamberDeviationViewSet, basename="stability-chamber-deviation")
router.register(r"stability/alerts", StabilityAlertViewSet, basename="stability-alert")

urlpatterns = router.urls
