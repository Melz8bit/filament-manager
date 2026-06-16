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
    path("prints/log/", views.LogPrintView.as_view(), name="log-print"),
]
