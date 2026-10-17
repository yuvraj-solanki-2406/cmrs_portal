from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CollectionViewSet, LoanRepaymentsView

router = DefaultRouter()
router.register("collections", CollectionViewSet, basename="collection")
urlpatterns = [
    path("loans/<int:loan_id>/repayments/", LoanRepaymentsView.as_view(), name="loan-repayments"),
    *router.urls,
]
