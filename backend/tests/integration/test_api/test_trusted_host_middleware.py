"""
Tests d'integration pour la protection TrustedHostMiddleware.

Verifie que la protection contre l'injection d'en-tete Host (ALLOWED_HOSTS,
cf. issue crypto-bot#72) est bien active sur l'application reelle, dans tous
les environnements (le middleware n'est plus conditionne par DEBUG).
"""

from fastapi.testclient import TestClient
from main import app


class TestTrustedHostMiddleware:
    """L'app FastAPI reelle (main.app) rejette les Host non autorises."""

    def test_allowed_host_is_accepted(self):
        """Un Host present dans ALLOWED_HOSTS (ex: localhost) passe normalement."""
        client = TestClient(app, base_url="http://localhost")
        response = client.get("/health")
        assert response.status_code == 200

    def test_internal_service_host_is_accepted(self):
        """Le nom du service docker-compose (appels serveur-a-serveur frontend->backend) passe."""
        client = TestClient(app, base_url="http://crypto-bot-backend")
        response = client.get("/health")
        assert response.status_code == 200

    def test_untrusted_host_is_rejected(self):
        """Un Host absent de ALLOWED_HOSTS est rejete (400), quel que soit DEBUG."""
        client = TestClient(app, base_url="http://evil.com")
        response = client.get("/health")
        assert response.status_code == 400
        assert "invalid host header" in response.text.lower()
