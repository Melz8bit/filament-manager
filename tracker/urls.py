from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("inventory/", views.SpoolListView.as_view(), name="spool-list"),
    path("inventory/add/", views.SpoolCreateView.as_view(), name="spool-add"),
    path(
        "inventory/<int:pk>/edit/", views.SpoolUpdateView.as_view(), name="spool-edit"
    ),
    path(
        "inventory/<int:pk>/delete/",
        views.SpoolDeleteView.as_view(),
        name="spool-delete",
    ),
    path("inventory/sku-lookup/", views.SkuLookupView.as_view(), name="sku-lookup"),
    path("inventory/products/", views.FilamentProductListView.as_view(), name="filament-product-list"),
    path("inventory/products/<int:pk>/edit/", views.FilamentProductUpdateView.as_view(), name="filament-product-edit"),
    path("inventory/products/<int:pk>/delete/", views.FilamentProductDeleteView.as_view(), name="filament-product-delete"),
    path("prints/log/", views.LogPrintView.as_view(), name="log-print"),
    path("prints/<int:pk>/assign/", views.SpoolAssignmentView.as_view(), name="spool-assignment"),
    path("queue/", views.QueueListView.as_view(), name="queue-list"),
    path("queue/add/", views.QueueAddView.as_view(), name="queue-add"),
    path("queue/<int:pk>/upload/", views.QueueUploadView.as_view(), name="queue-upload"),
    path("queue/<int:pk>/edit/", views.QueueEditView.as_view(), name="queue-edit"),
    path("queue/<int:pk>/delete/", views.QueueDeleteView.as_view(), name="queue-delete"),
    path("queue/fetch-title/", views.QueueFetchTitleView.as_view(), name="queue-fetch-title"),
    path("account/", views.AccountView.as_view(), name="account"),
    path("account/password/", views.AccountPasswordChangeView.as_view(), name="password-change"),
    path("history/", views.PrintHistoryView.as_view(), name="print-history"),
    path("prints/manual/", views.ManualEntryView.as_view(), name="manual-entry"),
    path("prints/slot-row/", views.SlotRowView.as_view(), name="slot-row"),
]
