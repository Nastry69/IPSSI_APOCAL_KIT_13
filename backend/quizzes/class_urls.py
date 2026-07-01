"""Endpoints de gestion des classes (montés sous /api/classes/)."""

from django.urls import path

from .views import (
    ClassesView,
    ClassProgressView,
    ClassroomDetailView,
    JoinClassView,
    StudentAttemptDetailView,
)

urlpatterns = [
    path("", ClassesView.as_view(), name="class-list-create"),
    path("join/", JoinClassView.as_view(), name="class-join"),
    # Release 2 — espace prof. Routes plus spécifiques AVANT <int:pk>/ générique
    # pour éviter que "progress" / "students" ne soient captés comme un id.
    path("<int:class_id>/progress/", ClassProgressView.as_view(), name="class-progress"),
    path(
        "<int:class_id>/students/<int:student_id>/attempts/<int:attempt_id>/",
        StudentAttemptDetailView.as_view(),
        name="class-student-attempt-detail",
    ),
    path("<int:pk>/", ClassroomDetailView.as_view(), name="class-detail"),
]
