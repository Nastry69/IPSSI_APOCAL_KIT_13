"""
Construction de l'export RGPD (droit à la portabilité, art. 20).

On assemble un dictionnaire JSON-sérialisable regroupant TOUTES les données
personnelles d'un utilisateur : son compte, son profil (dont le consentement),
ses quiz et les questions associées. Aucune donnée d'un autre utilisateur n'est
incluse (isolation stricte par `user`).
"""

from .models import get_or_create_profile


def build_user_export(user) -> dict:
    """Renvoie un dict JSON-sérialisable de toutes les données de `user`.

    Ne fait AUCUN accès aux données d'autres utilisateurs : on part de `user`
    et on suit ses relations (`user.quizzes` -> `quiz.questions`).
    """
    profile = get_or_create_profile(user)

    quizzes = []
    # `related_name="quizzes"` sur Quiz.user ; `related_name="questions"` sur Question.quiz
    for quiz in user.quizzes.all().order_by("created_at"):
        questions = [
            {
                "index": q.index,
                "prompt": q.prompt,
                "options": q.options,
                "correct_index": q.correct_index,
                "selected_index": q.selected_index,
            }
            for q in quiz.questions.all().order_by("index")
        ]
        quizzes.append(
            {
                "title": quiz.title,
                "source_text": quiz.source_text,
                "score": quiz.score,
                "created_at": quiz.created_at.isoformat(),
                "updated_at": quiz.updated_at.isoformat(),
                "questions": questions,
            }
        )

    return {
        "account": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined.isoformat(),
        },
        "profile": {
            "email_verified": profile.email_verified,
            "created_at": profile.created_at.isoformat(),
            "consentement": {
                "consent_accepted_at": (
                    profile.consent_accepted_at.isoformat() if profile.consent_accepted_at else None
                ),
                "consent_version": profile.consent_version or None,
            },
        },
        "quizzes": quizzes,
    }
