"""
Modèles de l'app accounts.

[Note pédagogique] On garde le modèle User standard de Django (simple et
robuste), et on lui ajoute un Profil 1-pour-1 pour les infos métier qui ne sont
pas dans User — ici `email_verified` (l'utilisateur a-t-il cliqué le lien de
confirmation envoyé par email ?).

Choix d'architecture « email = identifiant » : à l'inscription, on met
username = email (voir SignupSerializer). Le login se fait donc par email, sans
backend d'authentification custom. C'est le compromis le plus simple pour un
kit pédagogique (un vrai produit utiliserait souvent un User personnalisé avec
USERNAME_FIELD = 'email').
"""

from django.conf import settings
from django.db import models

# Version courante des CGU / politique de confidentialité. À incrémenter
# (nouvelle date) quand ces documents changent de façon substantielle.
CURRENT_CONSENT_VERSION = "2026-07-01"


class Profile(models.Model):
    """Informations complémentaires attachées à un utilisateur."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    # Validation "soft" : le compte fonctionne même si l'email n'est pas vérifié,
    # mais un bandeau invite l'utilisateur à cliquer le lien de confirmation.
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Consentement RGPD (traçabilité du consentement à l'inscription) ---
    # Date/heure à laquelle l'utilisateur a accepté les CGU et la politique de
    # confidentialité. NULL pour les comptes créés AVANT l'introduction du
    # consentement (rétrocompatibilité).
    consent_accepted_at = models.DateTimeField(null=True, blank=True)
    # Version des CGU/politique acceptée (permet de re-solliciter le consentement
    # si les documents changent). Vide pour les comptes historiques.
    consent_version = models.CharField(max_length=20, blank=True, default="")

    def __str__(self) -> str:
        return f"Profile<{self.user.email or self.user.username}>"


def get_or_create_profile(user) -> Profile:
    """Récupère (ou crée) le profil d'un utilisateur.

    Pratique pour les comptes créés AVANT l'ajout du modèle Profile (ils n'ont
    pas encore de profil) : on le crée à la volée plutôt que de planter.
    """
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile
