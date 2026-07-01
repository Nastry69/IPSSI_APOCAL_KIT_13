"""Tests des endpoints de classe : création (enseignant) + adhésion (code)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from quizzes.models import Answer, Attempt, Classroom, Question, Quiz

User = get_user_model()

pytestmark = pytest.mark.django_db


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def teacher():
    return User.objects.create_user(
        username="prof@test.com",
        email="prof@test.com",
        password="motdepasse123",
        role="teacher",
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        username="eleve@test.com",
        email="eleve@test.com",
        password="motdepasse123",
        role="student",
    )


# ---------------------------------------------------------------------------
# Release 2 — Espace prof : suivi de la progression des élèves d'une classe
# ---------------------------------------------------------------------------


def _make_quiz_with_questions(owner, title="Cours"):
    """Crée un quiz + 10 questions (correct_index=0 partout)."""
    quiz = Quiz.objects.create(user=owner, title=title, source_text="Lorem ipsum.")
    for i in range(1, 11):
        Question.objects.create(
            quiz=quiz,
            index=i,
            prompt=f"Q{i}",
            options=["A", "B", "C", "D"],
            correct_index=0,
        )
    return quiz


def _make_attempt(quiz, student, number, score, created_at=None):
    """Crée une tentative + ses Answer pour un élève (bypass endpoint answer)."""
    attempt = Attempt.objects.create(
        quiz=quiz, student=student, number=number, total=10, score=score
    )
    for q in quiz.questions.all():
        # Les `score` premières questions sont correctes (selected_index=0).
        correct = q.index <= score
        Answer.objects.create(
            attempt=attempt,
            question=q,
            selected_index=0 if correct else 1,
            is_correct=correct,
        )
    if created_at is not None:
        Attempt.objects.filter(pk=attempt.pk).update(created_at=created_at)
        attempt.refresh_from_db()
    return attempt


def test_teacher_creates_class_gets_code(teacher):
    resp = _client(teacher).post("/api/classes/", {"name": "Terminale B"}, format="json")
    assert resp.status_code == 201
    assert resp.data["name"] == "Terminale B"
    assert len(resp.data["code"]) == 6
    assert Classroom.objects.filter(teacher=teacher, name="Terminale B").exists()


def test_student_cannot_create_class(student):
    resp = _client(student).post("/api/classes/", {"name": "Interdit"}, format="json")
    assert resp.status_code == 403
    assert not Classroom.objects.exists()


def test_student_joins_with_code(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Terminale B", code="ABC234")
    resp = _client(student).post("/api/classes/join/", {"code": "abc234"}, format="json")
    assert resp.status_code == 200
    assert classroom.students.filter(pk=student.pk).exists()


def test_join_with_bad_code_returns_404(student):
    resp = _client(student).post("/api/classes/join/", {"code": "ZZZZZZ"}, format="json")
    assert resp.status_code == 404


def test_class_list_is_role_aware(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe A", code="AAA234")
    classroom.students.add(student)
    teacher_resp = _client(teacher).get("/api/classes/")
    assert {c["name"] for c in teacher_resp.data} == {"Classe A"}
    student_resp = _client(student).get("/api/classes/")
    assert {c["name"] for c in student_resp.data} == {"Classe A"}


def test_teacher_sees_roster(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe A", code="BBB234")
    classroom.students.add(student)
    resp = _client(teacher).get(f"/api/classes/{classroom.pk}/")
    assert resp.status_code == 200
    assert len(resp.data["students"]) == 1
    assert resp.data["students"][0]["email"] == "eleve@test.com"


# ---------------------------------------------------------------------------
# Endpoint A — GET /api/classes/<class_id>/progress/
# ---------------------------------------------------------------------------


def test_progress_requires_auth(teacher):
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="PRG001")
    resp = APIClient().get(f"/api/classes/{classroom.pk}/progress/")
    assert resp.status_code in (401, 403)


def test_student_gets_403_on_progress(teacher, student):
    """Un élève (non-teacher) est refusé par la permission IsTeacher (403)."""
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="PRG002")
    classroom.students.add(student)
    resp = _client(student).get(f"/api/classes/{classroom.pk}/progress/")
    assert resp.status_code == 403


def test_teacher_sees_progress_of_own_class(teacher, student):
    """Le teacher voit la progression agrégée des élèves de SA classe."""
    import datetime

    from django.utils import timezone

    classroom = Classroom.objects.create(teacher=teacher, name="C", code="PRG003")
    classroom.students.add(student)
    quiz = _make_quiz_with_questions(teacher, title="Chapitre 1")

    base = timezone.now()
    _make_attempt(quiz, student, number=1, score=4, created_at=base)
    _make_attempt(quiz, student, number=2, score=8, created_at=base + datetime.timedelta(hours=1))

    resp = _client(teacher).get(f"/api/classes/{classroom.pk}/progress/")
    assert resp.status_code == 200
    assert len(resp.data) == 1
    row = resp.data[0]
    assert row["student"]["id"] == student.id
    assert set(row["student"].keys()) == {"id", "first_name", "last_name", "username"}
    assert row["quizzes_taken"] == 2
    assert row["average_score"] == 6.0  # (4 + 8) / 2
    assert row["best_score"] == 8
    assert row["last_score"] == 8  # tentative la plus récente
    # evolution triée chronologiquement (score 4 puis 8).
    assert [e["score"] for e in row["evolution"]] == [4, 8]
    ev = row["evolution"][0]
    assert set(ev.keys()) == {
        "attempt_id",
        "quiz_id",
        "quiz_title",
        "number",
        "score",
        "total",
        "created_at",
    }
    assert ev["quiz_title"] == "Chapitre 1"


def test_progress_lists_all_students_including_without_attempts(teacher, student):
    """Un élève sans tentative apparaît quand même, avec des KPIs à None/0."""
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="PRG004")
    other_student = User.objects.create_user(
        username="eleve2@test.com", email="eleve2@test.com", password="x", role="student"
    )
    classroom.students.add(student, other_student)
    quiz = _make_quiz_with_questions(teacher)
    _make_attempt(quiz, student, number=1, score=5)

    resp = _client(teacher).get(f"/api/classes/{classroom.pk}/progress/")
    assert resp.status_code == 200
    by_id = {r["student"]["id"]: r for r in resp.data}
    assert by_id[student.id]["quizzes_taken"] == 1
    empty = by_id[other_student.id]
    assert empty["quizzes_taken"] == 0
    assert empty["average_score"] is None
    assert empty["best_score"] is None
    assert empty["last_score"] is None
    assert empty["evolution"] == []


def test_teacher_cannot_see_progress_of_other_teachers_class(teacher, student):
    """Une classe que le teacher ne possède pas → 404 (scoping sécurité)."""
    other_teacher = User.objects.create_user(
        username="prof2@test.com", email="prof2@test.com", password="x", role="teacher"
    )
    foreign_class = Classroom.objects.create(
        teacher=other_teacher, name="Pas la mienne", code="PRG005"
    )
    foreign_class.students.add(student)

    resp = _client(teacher).get(f"/api/classes/{foreign_class.pk}/progress/")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Endpoint B — GET /api/classes/<class_id>/students/<sid>/attempts/<aid>/
# ---------------------------------------------------------------------------


def _attempt_url(class_id, student_id, attempt_id):
    return f"/api/classes/{class_id}/students/{student_id}/attempts/{attempt_id}/"


def test_student_attempt_detail_requires_auth(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="ATT001")
    classroom.students.add(student)
    quiz = _make_quiz_with_questions(teacher)
    attempt = _make_attempt(quiz, student, number=1, score=6)
    resp = APIClient().get(_attempt_url(classroom.pk, student.pk, attempt.pk))
    assert resp.status_code in (401, 403)


def test_student_gets_403_on_attempt_detail(teacher, student):
    """Un élève (non-teacher) est refusé (403) sur l'endpoint espace prof."""
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="ATT002")
    classroom.students.add(student)
    quiz = _make_quiz_with_questions(teacher)
    attempt = _make_attempt(quiz, student, number=1, score=6)
    resp = _client(student).get(_attempt_url(classroom.pk, student.pk, attempt.pk))
    assert resp.status_code == 403


def test_teacher_sees_attempt_of_own_student(teacher, student):
    """Le teacher voit le détail (réponses) d'une tentative d'un élève de sa classe."""
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="ATT003")
    classroom.students.add(student)
    quiz = _make_quiz_with_questions(teacher, title="Chapitre 2")
    attempt = _make_attempt(quiz, student, number=1, score=7)

    resp = _client(teacher).get(_attempt_url(classroom.pk, student.pk, attempt.pk))
    assert resp.status_code == 200
    assert resp.data["id"] == attempt.pk
    assert resp.data["number"] == 1
    assert resp.data["score"] == 7
    assert resp.data["total"] == 10
    assert len(resp.data["answers"]) == 10
    # 7 bonnes réponses (index 1..7), 3 mauvaises (8..10).
    wrong = sorted(a["index"] for a in resp.data["answers"] if not a["is_correct"])
    assert wrong == [8, 9, 10]


def test_teacher_cannot_see_attempt_of_student_not_in_class(teacher, student):
    """Un élève qui n'est PAS membre de la classe → 404 (même si la tentative existe)."""
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="ATT004")
    # student n'est PAS ajouté à la classe.
    quiz = _make_quiz_with_questions(teacher)
    attempt = _make_attempt(quiz, student, number=1, score=6)

    resp = _client(teacher).get(_attempt_url(classroom.pk, student.pk, attempt.pk))
    assert resp.status_code == 404


def test_teacher_cannot_see_attempt_via_class_they_dont_own(teacher, student):
    """La classe n'appartient pas au teacher → 404 (scoping sécurité)."""
    other_teacher = User.objects.create_user(
        username="prof3@test.com", email="prof3@test.com", password="x", role="teacher"
    )
    foreign_class = Classroom.objects.create(teacher=other_teacher, name="Autre", code="ATT005")
    foreign_class.students.add(student)
    quiz = _make_quiz_with_questions(other_teacher)
    attempt = _make_attempt(quiz, student, number=1, score=6)

    resp = _client(teacher).get(_attempt_url(foreign_class.pk, student.pk, attempt.pk))
    assert resp.status_code == 404


def test_teacher_cannot_see_attempt_belonging_to_another_student(teacher, student):
    """L'attempt appartient à un AUTRE élève que celui de l'URL → 404.

    Empêche de fabriquer une URL avec l'id d'un élève de la classe mais l'id
    d'une tentative appartenant à quelqu'un d'autre.
    """
    classroom = Classroom.objects.create(teacher=teacher, name="C", code="ATT006")
    other_student = User.objects.create_user(
        username="eleve3@test.com", email="eleve3@test.com", password="x", role="student"
    )
    classroom.students.add(student, other_student)
    quiz = _make_quiz_with_questions(teacher)
    # Tentative appartenant à other_student.
    attempt_other = _make_attempt(quiz, other_student, number=1, score=9)

    # On demande la tentative d'other_student en la faisant passer pour student.
    resp = _client(teacher).get(_attempt_url(classroom.pk, student.pk, attempt_other.pk))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# F4 — CRUD classes & élèves (espace prof)
# ---------------------------------------------------------------------------


@pytest.fixture
def other_teacher():
    return User.objects.create_user(
        username="autre-prof@test.com",
        email="autre-prof@test.com",
        password="motdepasse123",
        role="teacher",
    )


# --- PATCH /api/classes/<id>/ : renommer ---


def test_teacher_renames_own_class(teacher):
    classroom = Classroom.objects.create(teacher=teacher, name="Ancien nom", code="REN001")
    resp = _client(teacher).patch(
        f"/api/classes/{classroom.pk}/", {"name": "Nouveau nom"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["name"] == "Nouveau nom"
    classroom.refresh_from_db()
    assert classroom.name == "Nouveau nom"


def test_teacher_renames_class_with_title_alias(teacher):
    """Le contrat accepte `name` ; on tolère aussi `title` comme alias."""
    classroom = Classroom.objects.create(teacher=teacher, name="Ancien", code="REN002")
    resp = _client(teacher).patch(
        f"/api/classes/{classroom.pk}/", {"title": "Via title"}, format="json"
    )
    assert resp.status_code == 200
    classroom.refresh_from_db()
    assert classroom.name == "Via title"


def test_rename_empty_name_is_rejected(teacher):
    classroom = Classroom.objects.create(teacher=teacher, name="Garde", code="REN003")
    resp = _client(teacher).patch(f"/api/classes/{classroom.pk}/", {"name": "  "}, format="json")
    assert resp.status_code == 400
    classroom.refresh_from_db()
    assert classroom.name == "Garde"


def test_teacher_cannot_rename_other_teachers_class(teacher, other_teacher):
    """Renommer la classe d'un autre prof → 404 (scoping sécurité)."""
    foreign = Classroom.objects.create(teacher=other_teacher, name="Pas la mienne", code="REN004")
    resp = _client(teacher).patch(
        f"/api/classes/{foreign.pk}/", {"name": "Piratage"}, format="json"
    )
    assert resp.status_code == 404
    foreign.refresh_from_db()
    assert foreign.name == "Pas la mienne"


def test_student_cannot_rename_class(teacher, student):
    """Un non-teacher est refusé (403) par la permission IsTeacher."""
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="REN005")
    classroom.students.add(student)
    resp = _client(student).patch(f"/api/classes/{classroom.pk}/", {"name": "X"}, format="json")
    assert resp.status_code == 403


# --- DELETE /api/classes/<id>/ : supprimer ---


def test_teacher_deletes_own_class(teacher):
    classroom = Classroom.objects.create(teacher=teacher, name="À supprimer", code="DEL001")
    resp = _client(teacher).delete(f"/api/classes/{classroom.pk}/")
    assert resp.status_code == 204
    assert not Classroom.objects.filter(pk=classroom.pk).exists()


def test_teacher_cannot_delete_other_teachers_class(teacher, other_teacher):
    foreign = Classroom.objects.create(teacher=other_teacher, name="Autre", code="DEL002")
    resp = _client(teacher).delete(f"/api/classes/{foreign.pk}/")
    assert resp.status_code == 404
    assert Classroom.objects.filter(pk=foreign.pk).exists()


def test_student_cannot_delete_class(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="DEL003")
    resp = _client(student).delete(f"/api/classes/{classroom.pk}/")
    assert resp.status_code == 403
    assert Classroom.objects.filter(pk=classroom.pk).exists()


# --- POST /api/classes/<id>/students/ : ajouter un élève ---


def test_teacher_adds_student_by_email(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="ADD001")
    resp = _client(teacher).post(
        f"/api/classes/{classroom.pk}/students/",
        {"identifier": "eleve@test.com"},
        format="json",
    )
    assert resp.status_code == 200
    assert classroom.students.filter(pk=student.pk).exists()
    # La réponse renvoie le roster à jour.
    assert any(s["id"] == student.pk for s in resp.data["students"])


def test_teacher_adds_student_by_username(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="ADD002")
    resp = _client(teacher).post(
        f"/api/classes/{classroom.pk}/students/",
        {"identifier": student.username},
        format="json",
    )
    assert resp.status_code == 200
    assert classroom.students.filter(pk=student.pk).exists()


def test_add_nonexistent_email_returns_404(teacher):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="ADD003")
    resp = _client(teacher).post(
        f"/api/classes/{classroom.pk}/students/",
        {"identifier": "personne@nulle-part.com"},
        format="json",
    )
    assert resp.status_code == 404
    assert classroom.students.count() == 0


def test_add_a_teacher_as_student_returns_404(teacher, other_teacher):
    """L'identifiant existe mais l'utilisateur n'est pas un élève → 404."""
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="ADD004")
    resp = _client(teacher).post(
        f"/api/classes/{classroom.pk}/students/",
        {"identifier": other_teacher.email},
        format="json",
    )
    assert resp.status_code == 404
    assert classroom.students.count() == 0


def test_teacher_cannot_add_student_to_other_teachers_class(teacher, other_teacher, student):
    foreign = Classroom.objects.create(teacher=other_teacher, name="Autre", code="ADD005")
    resp = _client(teacher).post(
        f"/api/classes/{foreign.pk}/students/",
        {"identifier": "eleve@test.com"},
        format="json",
    )
    assert resp.status_code == 404
    assert foreign.students.count() == 0


def test_student_cannot_add_student(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="ADD006")
    classroom.students.add(student)
    resp = _client(student).post(
        f"/api/classes/{classroom.pk}/students/",
        {"identifier": "eleve@test.com"},
        format="json",
    )
    assert resp.status_code == 403


# --- DELETE /api/classes/<id>/students/<student_id>/ : retirer un élève ---


def test_teacher_removes_student(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="RM001")
    classroom.students.add(student)
    resp = _client(teacher).delete(f"/api/classes/{classroom.pk}/students/{student.pk}/")
    assert resp.status_code == 204
    assert not classroom.students.filter(pk=student.pk).exists()


def test_remove_student_not_in_class_returns_404(teacher, student):
    """Retirer un élève qui n'est pas membre → 404."""
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="RM002")
    resp = _client(teacher).delete(f"/api/classes/{classroom.pk}/students/{student.pk}/")
    assert resp.status_code == 404


def test_teacher_cannot_remove_student_from_other_teachers_class(teacher, other_teacher, student):
    foreign = Classroom.objects.create(teacher=other_teacher, name="Autre", code="RM003")
    foreign.students.add(student)
    resp = _client(teacher).delete(f"/api/classes/{foreign.pk}/students/{student.pk}/")
    assert resp.status_code == 404
    assert foreign.students.filter(pk=student.pk).exists()


def test_student_cannot_remove_student(teacher, student):
    classroom = Classroom.objects.create(teacher=teacher, name="Classe", code="RM004")
    classroom.students.add(student)
    resp = _client(student).delete(f"/api/classes/{classroom.pk}/students/{student.pk}/")
    assert resp.status_code == 403
    assert classroom.students.filter(pk=student.pk).exists()
