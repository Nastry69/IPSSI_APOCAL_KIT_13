from django.urls import path

from .views import (
    GenerateNoteView,
    GenerateQuizView,
    GenerateSummaryView,
    PingView,
    StudyDocDetailView,
    StudyDocListView,
)

urlpatterns = [
    path("ping/", PingView.as_view(), name="llm-ping"),
    path("generate-quiz/", GenerateQuizView.as_view(), name="llm-generate-quiz"),
    path("generate-note/", GenerateNoteView.as_view(), name="llm-generate-note"),
    path("generate-summary/", GenerateSummaryView.as_view(), name="llm-generate-summary"),
    path("study-docs/", StudyDocListView.as_view(), name="llm-study-docs"),
    path("study-docs/<int:pk>/", StudyDocDetailView.as_view(), name="llm-study-doc-detail"),
]
