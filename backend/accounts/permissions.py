"""Permissions DRF basées sur le rôle utilisateur (élève / enseignant).

[Note pédagogique] On centralise ici le contrôle d'accès par rôle pour le
réutiliser sur les endpoints réservés aux enseignants (gestion de classe, suivi
des élèves) ou aux élèves. Le compte enseignant est « mixte » : `IsTeacher`
OUVRE les capacités prof sans retirer l'accès élève.
"""

from rest_framework.permissions import BasePermission


class IsTeacher(BasePermission):
    message = "Action réservée aux comptes enseignants."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_teacher", False))


class IsStudent(BasePermission):
    message = "Action réservée aux comptes élèves."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_student", False))
