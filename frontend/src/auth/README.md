# 🔐 Authentication Module

Ce module fournit des utilitaires d'authentification pour le client Streamlit, basés sur les tests du notebook `01_auth_endpoints_testing.ipynb`.

## 📁 Structure

```
auth/
├── __init__.py          # Exports du module
├── config.py            # Configuration API (URLs, headers)
├── api_client.py        # Client API pour les endpoints d'authentification
├── auth_manager.py      # Gestionnaire d'authentification Streamlit
├── utils.py             # Fonctions utilitaires
├── examples.py          # Exemples d'utilisation
└── README.md           # Cette documentation
```

## 🚀 Installation

Les dépendances requises sont déjà dans `requirements.txt` :
- `requests` - Pour les appels API
- `streamlit` - Framework web

## 📖 Utilisation

### 1. Configuration de base

Assurez-vous que l'API backend est en cours d'exécution sur `http://localhost:8009`.

Pour modifier l'URL de l'API, éditez `auth/config.py` :

```python
BASE_URL = "http://localhost:8009"  # Changez selon votre environnement
```

### 2. Utilisation simple avec AuthManager

```python
import streamlit as st
from auth.auth_manager import AuthManager

# Initialiser le gestionnaire d'authentification
auth_manager = AuthManager()

# Vérifier la santé de l'API
is_healthy, message = auth_manager.check_health()
if not is_healthy:
    st.error(f"API non disponible: {message}")

# Login
success, message = auth_manager.login("username", "password")
if success:
    st.success(message)
    # Récupérer les infos utilisateur
    user_success, user_data = auth_manager.get_current_user()
    if user_success:
        st.write(f"Bienvenue {user_data['username']}")

# Logout
success, message = auth_manager.logout()
```

### 3. Intégration avec les pages existantes

#### Remplacer la page de login

Dans `page/login_page.py`, remplacez la fonction `authenticate_user` par :

```python
from auth.auth_manager import AuthManager
from auth.utils import validate_email

def login_page(guest_mode=False):
    st.title("Login Page")
    
    auth_manager = AuthManager()
    
    # Vérifier que l'API est disponible
    is_healthy, health_msg = auth_manager.check_health()
    if not is_healthy:
        st.error(f"⚠️ API non disponible: {health_msg}")
        return
    
    email = st.text_input("E-mail")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if not (email and password):
            st.error("Veuillez fournir l'email et le mot de passe")
        else:
            success, message = auth_manager.login(email, password)
            if success:
                st.session_state['authenticated'] = True
                st.session_state['page'] = 'app'
                st.rerun()
            else:
                st.error(message)
```

#### Remplacer la page d'inscription

Dans `page/signup_page.py` :

```python
from auth.auth_manager import AuthManager
from auth.utils import validate_email, validate_password_strength

def signup_page():
    st.title("Sign Up Page")
    
    auth_manager = AuthManager()
    
    email = st.text_input("Email")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    
    if st.button("Register"):
        # Validations
        if not validate_email(email):
            st.error("Email invalide")
            return
        
        if password != confirm_password:
            st.error("Les mots de passe ne correspondent pas")
            return
        
        is_strong, pwd_msg = validate_password_strength(password)
        if not is_strong:
            st.error(pwd_msg)
            return
        
        # Enregistrement
        success, message = auth_manager.register(
            email=email,
            username=username,
            password=password
        )
        
        if success:
            st.success(message)
            st.session_state['page'] = 'app'
            st.rerun()
        else:
            st.error(message)
```

### 4. Utilisation directe du client API

Pour un contrôle plus fin :

```python
from auth.api_client import AuthAPIClient

client = AuthAPIClient()

# Enregistrement
response = client.register(
    email="user@example.com",
    username="myuser",
    password="SecurePass123!"
)

if response.success:
    access_token = response.data['access_token']
    refresh_token = response.data['refresh_token']
    print(f"Token d'accès: {access_token}")

# Login avec JSON
response = client.login_json("myuser", "SecurePass123!")

# Login avec OAuth2
response = client.login_oauth2("myuser", "SecurePass123!")

# Rafraîchir le token
response = client.refresh_token(refresh_token)

# Obtenir les infos utilisateur
response = client.get_current_user(access_token)
if response.success:
    user_data = response.data
    print(f"User ID: {user_data['id']}")

# Déconnexion
response = client.logout(refresh_token)

# Déconnexion de toutes les sessions
response = client.logout_all(user_id)
```

## 🔑 Endpoints supportés

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/auth/register` | POST | Enregistrer un nouvel utilisateur |
| `/auth/login` | POST | Connexion OAuth2 (form-data) |
| `/auth/login/json` | POST | Connexion JSON |
| `/auth/refresh` | POST | Rafraîchir le token d'accès |
| `/auth/logout` | POST | Déconnexion de la session actuelle |
| `/auth/logout-all` | POST | Déconnexion de toutes les sessions |
| `/users/me` | GET | Obtenir les infos de l'utilisateur actuel |

## 🛠️ Fonctions utilitaires

### Validation

```python
from auth.utils import validate_email, validate_password_strength

# Valider un email
is_valid = validate_email("user@example.com")

# Valider la force du mot de passe
is_strong, message = validate_password_strength("MyPass123!")
if not is_strong:
    print(message)
```

### Formatage

```python
from auth.utils import format_user_display, mask_token

# Formater les données utilisateur pour l'affichage
user_display = format_user_display(user_data)
st.markdown(user_display)

# Masquer un token pour l'affichage
masked = mask_token(access_token, visible_chars=10)
print(masked)  # "abcdef1234...********"
```

### Génération de données de test

```python
from auth.utils import generate_test_user_data

# Générer des données de test uniques
test_data = generate_test_user_data()
# {
#     "email": "testuser_abc12345_1234567890@example.com",
#     "username": "testuser_abc12345",
#     "first_name": "Test",
#     "last_name": "User",
#     "password": "TestPassword123!"
# }
```

## 📦 Session State

Le module utilise les variables de session Streamlit suivantes :

- `access_token` : Token d'accès JWT
- `refresh_token` : Token de rafraîchissement
- `user_data` : Données de l'utilisateur connecté
- `authenticated` : État d'authentification (bool)

## 🔒 Sécurité

- Les tokens sont stockés uniquement dans la session Streamlit (pas de stockage persistant local)
- Les mots de passe ne sont jamais stockés, seulement transmis à l'API
- Validation côté client avant l'envoi à l'API
- Support du rafraîchissement automatique des tokens expirés

## 🧪 Tests

Voir le notebook `01_auth_endpoints_testing.ipynb` pour des exemples de tests complets.

## 📝 Exemples complets

Consultez `auth/examples.py` pour des exemples d'intégration complète avec :
- Page de login
- Page d'inscription
- Profil utilisateur
- Protection de pages

## 🐛 Dépannage

### L'API n'est pas accessible

```python
auth_manager = AuthManager()
is_healthy, message = auth_manager.check_health()
if not is_healthy:
    print(f"Erreur: {message}")
    # Vérifiez que le backend est démarré sur http://localhost:8009
```

### Token expiré

Le module tente automatiquement de rafraîchir les tokens expirés :

```python
# Ceci est géré automatiquement dans auth_manager.get_current_user()
# Mais vous pouvez aussi le faire manuellement :
success, message = auth_manager.refresh_access_token()
```

### Erreurs de connexion

```python
from auth.api_client import AuthAPIClient

client = AuthAPIClient()
response = client.login_json("username", "password")

if not response.success:
    print(f"Status: {response.status_code}")
    print(f"Error: {response.error or response.data}")
```

## 📚 Références

- Notebook source : `src/client/notebooks/01_auth_endpoints_testing.ipynb`
- API Backend : `http://localhost:8009/api/v1/docs` (Swagger UI)
- Documentation FastAPI : `docs/api/`
