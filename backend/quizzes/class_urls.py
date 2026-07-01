"""Endpoints de gestion des classes (montés sous /api/classes/)."""

from django.urls import path

from .views import ClassesView, ClassroomDetailView, JoinClassView

urlpatterns = [
    path("", ClassesView.as_view(), name="class-list-create"),
    path("join/", JoinClassView.as_view(), name="class-join"),
    path("<int:pk>/", ClassroomDetailView.as_view(), name="class-detail"),
]
