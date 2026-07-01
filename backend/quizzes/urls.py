from django.urls import path

from .views import (
    AnswerQuizView,
    AttemptDetailView,
    AttemptListView,
    MistakesView,
    QuizDetailView,
    QuizListView,
    StatsView,
)

urlpatterns = [
    path("", QuizListView.as_view(), name="quiz-list"),
    # MVP2 (Lot 6) — placés AVANT <int:pk> pour ne pas être captés comme un id.
    path("stats/", StatsView.as_view(), name="quiz-stats"),
    path("mistakes/", MistakesView.as_view(), name="quiz-mistakes"),
    # Release 2 — historique des tentatives. Routes plus spécifiques AVANT
    # <int:pk> générique pour éviter la capture (answer/attempts ne sont pas des id).
    path("<int:pk>/answer/", AnswerQuizView.as_view(), name="quiz-answer"),
    path("<int:pk>/attempts/", AttemptListView.as_view(), name="quiz-attempts"),
    path(
        "<int:pk>/attempts/<int:attempt_id>/",
        AttemptDetailView.as_view(),
        name="quiz-attempt-detail",
    ),
    path("<int:pk>/", QuizDetailView.as_view(), name="quiz-detail"),
]
