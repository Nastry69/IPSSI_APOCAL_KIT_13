"""Middleware de sécurité : en-têtes OWASP non gérés nativement par Django.

Le `SecurityMiddleware` de Django pose déjà HSTS, X-Content-Type-Options,
X-Frame-Options et Referrer-Policy. Il ne pose NI `Permissions-Policy` NI
`Content-Security-Policy` : ce middleware les ajoute sur toutes les réponses,
sans dépendance tierce (pas besoin de django-csp).

Ces deux en-têtes ne dépendent pas d'HTTPS : on les applique dans TOUS les
environnements (défense en profondeur, dev comme prod).
"""

# Permissions-Policy : on neutralise les APIs navigateur non utilisées par l'app
# (réduit la surface d'attaque / l'abus de fonctionnalités puissantes).
PERMISSIONS_POLICY = (
    "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=()"
)

# Content-Security-Policy volontairement MODÉRÉE : 'unsafe-inline' est requis par
# Swagger UI (drf-spectacular). `frame-ancestors 'none'` complète X-Frame-Options
# (anti-clickjacking, cross-browser). À durcir (nonces, retrait de unsafe-inline)
# si l'UI Swagger est retirée de la production.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware:
    """Ajoute `Permissions-Policy` et `Content-Security-Policy` à chaque réponse."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # setdefault : ne pas écraser un en-tête déjà posé en amont.
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response
