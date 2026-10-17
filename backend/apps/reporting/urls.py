from django.urls import path, register_converter

from . import views


class KindConverter:
    regex = "collection|submission|deposit"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(KindConverter, "kind")

urlpatterns = [
    path("dashboard/summary/", views.SummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/records/", views.StageRecordsView.as_view(), name="dashboard-records"),
    path("dashboard/branch-summary/", views.BranchSummaryView.as_view(), name="dashboard-branch-summary"),
    path("reports/discrepancies/", views.DiscrepancyReportView.as_view(), name="report-discrepancies"),
    path("reports/mismatches/", views.MismatchReportView.as_view(), name="report-mismatches"),
    path("reports/lifecycle/<kind:kind>/<int:pk>/", views.LifecycleView.as_view(), name="report-lifecycle"),
    path("export/collections.csv", views.CollectionsCsv.as_view(), name="export-collections"),
    path("export/submissions.csv", views.SubmissionsCsv.as_view(), name="export-submissions"),
    path("export/deposits.csv", views.DepositsCsv.as_view(), name="export-deposits"),
    path("reports/discrepancies.csv", views.DiscrepanciesCsv.as_view(), name="export-discrepancies"),
    path("reports/mismatches.csv", views.MismatchesCsv.as_view(), name="export-mismatches"),
]
