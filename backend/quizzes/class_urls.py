"""Endpoints de gestion des classes (montés sous /api/classes/)."""

from django.urls import path

from .views import (
    ClassesView,
    ClassProgressView,
    ClassroomDetailView,
    ClassStudentDetailView,
    ClassStudentsView,
    JoinClassView,
    StudentAttemptDetailView,
)

urlpatterns = [
    path("", ClassesView.as_view(), name="class-list-create"),
    path("join/", JoinClassView.as_view(), name="class-join"),
    # Release 2 — espace prof. Routes plus spécifiques AVANT <int:pk>/ générique
    # pour éviter que "progress" / "students" ne soient captés comme un id.
    path("<int:class_id>/progress/", ClassProgressView.as_view(), name="class-progress"),
    # La route « détail d'une tentative d'un élève » (4 segments, se termine par
    # attempts/<id>/) DOIT rester AVANT la route « retrait d'élève » (2 segments)
    # pour ne pas être masquée.
    path(
        "<int:class_id>/students/<int:student_id>/attempts/<int:attempt_id>/",
        StudentAttemptDetailView.as_view(),
        name="class-student-attempt-detail",
    ),
    # F4 — CRUD élèves. AVANT <int:pk>/ générique.
    path("<int:pk>/students/", ClassStudentsView.as_view(), name="class-students"),
    path(
        "<int:pk>/students/<int:student_id>/",
        ClassStudentDetailView.as_view(),
        name="class-student-detail",
    ),
    # PATCH/DELETE/GET sur la classe elle-même — route générique en DERNIER.
    path("<int:pk>/", ClassroomDetailView.as_view(), name="class-detail"),
]
