"""Tests des endpoints de classe : création (enseignant) + adhésion (code)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from quizzes.models import Classroom

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
