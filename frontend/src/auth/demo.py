"""
Démonstration complète du module d'authentification.
Exemple d'utilisation sans Streamlit (pour tests).

Pour tester avec Streamlit, voir auth/examples.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth import (  # noqa: E402
    AuthAPIClient,
    validate_email,
    validate_password_strength,
    generate_test_user_data,
    mask_token,
)


def demo_api_client():
    """Démonstration du client API."""
    print("\n" + "=" * 60)
    print("🔐 DÉMONSTRATION DU CLIENT API")
    print("=" * 60 + "\n")

    client = AuthAPIClient()

    # 1. Health Check
    print("1️⃣  Test de santé de l'API...")
    response = client.health_check()
    if response.success:
        print("   ✅ API is healthy")
        print(f"   📊 Response: {response.data}")
    else:
        print(f"   ❌ API not available: {response.error}")
        print("   ⚠️  Assurez-vous que le backend est démarré sur http://localhost:8009")
        return False

    # 2. Générer des données de test
    print("\n2️⃣  Génération de données de test...")
    user_data = generate_test_user_data()
    print(f"   📝 Email: {user_data['email']}")
    print(f"   👤 Username: {user_data['username']}")
    print(f"   🔒 Password: {mask_token(user_data['password'], 5)}")

    # 3. Validation
    print("\n3️⃣  Validation des données...")
    email_valid = validate_email(user_data["email"])
    print(f"   {'✅' if email_valid else '❌'} Email valide: {email_valid}")

    pwd_valid, pwd_msg = validate_password_strength(user_data["password"])
    print(f"   {'✅' if pwd_valid else '❌'} Mot de passe: {pwd_msg}")

    # 4. Enregistrement
    print("\n4️⃣  Enregistrement d'un nouvel utilisateur...")
    response = client.register(
        email=user_data["email"],
        username=user_data["username"],
        password=user_data["password"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
    )

    if response.success:
        print("   ✅ Enregistrement réussi!")
        access_token = response.data.get("access_token")
        refresh_token = response.data.get("refresh_token")
        print(f"   🔑 Access Token: {mask_token(access_token, 20)}")
        print(f"   🔄 Refresh Token: {mask_token(refresh_token, 20)}")
    else:
        print(f"   ❌ Enregistrement échoué: {response.data}")
        # L'utilisateur existe peut-être déjà, essayons de nous connecter
        print("   ℹ️  Tentative de connexion avec un utilisateur existant...")

        # Utiliser des credentials de test connus
        test_login = "testuser"
        test_password = "TestPassword123!"  # nosec B105 - demo credentials
        response = client.login_json(test_login, test_password)

        if response.success:
            access_token = response.data.get("access_token")
            refresh_token = response.data.get("refresh_token")
            print("   ✅ Connexion réussie avec utilisateur de test!")
        else:
            print("   ❌ Impossible de se connecter")
            return False

    # 5. Login JSON
    print("\n5️⃣  Test de connexion avec JSON...")
    response = client.login_json(user_data["username"], user_data["password"])

    if response.success:
        print("   ✅ Connexion JSON réussie!")
        new_access_token = response.data.get("access_token")
        print(f"   🔑 Nouveau Access Token: {mask_token(new_access_token, 20)}")
    else:
        print(f"   ⚠️  Connexion JSON échouée: {response.data}")

    # 6. Obtenir les infos utilisateur
    print("\n6️⃣  Récupération des informations utilisateur...")
    response = client.get_current_user(access_token)

    if response.success:
        print("   ✅ Informations utilisateur récupérées!")
        user_info = response.data
        print(f"   🆔 User ID: {user_info.get('id')}")
        print(f"   👤 Username: {user_info.get('username')}")
        print(f"   📧 Email: {user_info.get('email')}")
        user_id = user_info.get("id")
    else:
        print(f"   ❌ Impossible de récupérer les infos: {response.data}")
        user_id = None

    # 7. Rafraîchir le token
    print("\n7️⃣  Rafraîchissement du token...")
    response = client.refresh_token(refresh_token)

    if response.success:
        print("   ✅ Token rafraîchi!")
        new_access_token = response.data.get("access_token")
        print(f"   🔑 Nouveau Access Token: {mask_token(new_access_token, 20)}")
        access_token = new_access_token
    else:
        print(f"   ⚠️  Rafraîchissement échoué: {response.data}")

    # 8. Logout
    print("\n8️⃣  Déconnexion...")
    response = client.logout(refresh_token)

    if response.success:
        print("   ✅ Déconnexion réussie!")
    else:
        print(f"   ⚠️  Déconnexion échouée: {response.data}")

    # 9. Logout all (si on a l'user_id)
    if user_id:
        print("\n9️⃣  Déconnexion de toutes les sessions...")
        response = client.logout_all(user_id)

        if response.success:
            print("   ✅ Toutes les sessions fermées!")
        else:
            print(f"   ⚠️  Logout all échoué: {response.data}")

    print("\n" + "=" * 60)
    print("✅ Démonstration terminée!")
    print("=" * 60 + "\n")

    return True


def demo_validators():
    """Démonstration des validateurs."""
    print("\n" + "=" * 60)
    print("🔍 DÉMONSTRATION DES VALIDATEURS")
    print("=" * 60 + "\n")

    # Test emails
    print("📧 Validation d'emails:\n")
    test_emails = [
        "user@example.com",
        "invalid-email",
        "test.user+tag@domain.co.uk",
        "@invalid.com",
        "no-domain@",
    ]

    for email in test_emails:
        is_valid = validate_email(email)
        status = "✅" if is_valid else "❌"
        print(f"   {status} {email:30} -> {is_valid}")

    # Test passwords
    print("\n🔒 Validation de mots de passe:\n")
    test_passwords = [
        ("weak", "Mot de passe faible"),
        ("NoNumbers!", "Sans chiffres"),
        ("nonumbers123", "Sans majuscule"),
        ("NOUPPER123", "Sans minuscule"),
        ("Short1!", "Trop court"),
        ("StrongPassword123!", "Fort et sécurisé"),
    ]

    for password, description in test_passwords:
        is_valid, message = validate_password_strength(password)
        status = "✅" if is_valid else "❌"
        print(f"   {status} {description:20} -> {message}")

    print("\n" + "=" * 60 + "\n")


def main():
    """Point d'entrée principal."""
    print("\n" + "🚀" * 30)
    print(" " * 20 + "MODULE D'AUTHENTIFICATION")
    print(" " * 15 + "Démonstration des fonctionnalités")
    print("🚀" * 30)

    # Démonstration des validateurs (sans API)
    demo_validators()

    # Démonstration du client API (nécessite l'API en cours d'exécution)
    print("\n💡 Pour tester le client API, assurez-vous que:")
    print("   1. Le backend FastAPI est démarré (http://localhost:8009)")
    print("   2. La base de données PostgreSQL est accessible")
    print("   3. Les migrations sont appliquées\n")

    input("Appuyez sur Entrée pour continuer avec les tests API... ")

    success = demo_api_client()

    if success:
        print("\n🎉 Toutes les démonstrations ont réussi!")
        print("\n📚 Prochaines étapes:")
        print("   - Voir auth/examples.py pour l'intégration Streamlit")
        print("   - Lire auth/README.md pour la documentation complète")
        print("   - Consulter auth/MIGRATION.md pour migrer votre code")
        return 0
    else:
        print("\n⚠️  Certains tests ont échoué")
        print("   Vérifiez que le backend est bien démarré")
        return 1


if __name__ == "__main__":
    sys.exit(main())
