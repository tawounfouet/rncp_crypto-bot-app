# 🔄 Guide de Migration vers le Module Auth

Ce guide vous aide à migrer vos pages existantes pour utiliser le nouveau module d'authentification.

## 📋 Étapes de Migration

### 1. Remplacer `utils/db_handler.py`

#### Avant (ancien code)
```python
# utils/db_handler.py
def authenticate_user(email, password):
    # Code PostgreSQL direct
    conn = get_db_connection()
    cursor = conn.cursor()
    # ...
```

#### Après (nouveau code)
```python
# Vous pouvez supprimer ou simplifier db_handler.py
# L'authentification se fait maintenant via l'API

# OU garder pour la compatibilité:
from auth import AuthManager

def authenticate_user(email, password):
    """Wrapper pour compatibilité - utilise maintenant l'API."""
    auth_manager = AuthManager()
    success, message = auth_manager.login(email, password)
    return success
```

### 2. Mettre à jour `page/login_page.py`

#### Avant
```python
from utils.db_handler import authenticate_user

def login_page(guest_mode=False):
    email = st.text_input("E-mail")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if authenticate_user(email, password):
            st.session_state['authenticated'] = True
            st.session_state['page'] = 'app'
            st.rerun()
```

#### Après
```python
from auth import AuthManager

def login_page(guest_mode=False):
    auth_manager = AuthManager()
    
    # Vérifier la santé de l'API
    is_healthy, health_msg = auth_manager.check_health()
    if not is_healthy:
        st.error(f"⚠️ API non disponible: {health_msg}")
        st.info("Démarrez le backend: cd /path/to/backend && uvicorn main:app")
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

### 3. Mettre à jour `page/signup_page.py`

#### Avant
```python
from utils.otp_handler import generate_otp, send_email
from utils.db_handler import save_user, verify_duplicate_user

def signup_page(extra_input_params=False, confirmPass=False):
    st.session_state['email'] = st.text_input("Email")
    st.session_state['password'] = st.text_input("Password", type='password')
    
    if st.button("Register"):
        st.session_state['verifying'] = True
        # OTP logic...
```

#### Après
```python
from auth import AuthManager, validate_email, validate_password_strength

def signup_page(extra_input_params=False, confirmPass=False):
    auth_manager = AuthManager()
    
    email = st.text_input("Email")
    
    # Validation immédiate
    if email and not validate_email(email):
        st.error("Format d'email invalide")
    
    password = st.text_input("Password", type='password')
    
    # Afficher la force du mot de passe
    if password:
        is_strong, pwd_msg = validate_password_strength(password)
        if is_strong:
            st.success(pwd_msg)
        else:
            st.warning(pwd_msg)
    
    confirm_password = st.text_input("Confirm Password", type='password')
    
    if st.button("Register"):
        # Validations
        if not (email and password):
            st.error("Email et mot de passe requis")
            return
        
        if not validate_email(email):
            st.error("Format d'email invalide")
            return
        
        if password != confirm_password:
            st.error("Les mots de passe ne correspondent pas")
            return
        
        is_strong, pwd_msg = validate_password_strength(password)
        if not is_strong:
            st.error(pwd_msg)
            return
        
        # Enregistrement via API (pas d'OTP pour l'instant)
        success, message = auth_manager.register(
            email=email,
            username=email.split('@')[0],  # Utiliser partie email comme username
            password=password
        )
        
        if success:
            st.success(message)
            st.info("Vous êtes maintenant connecté!")
            st.session_state['page'] = 'app'
            st.rerun()
        else:
            st.error(message)
```

### 4. Ajouter un profil utilisateur à `page/app.py`

```python
from auth import AuthManager, format_user_display

def app_page():
    auth_manager = AuthManager()
    
    # Vérifier l'authentification
    if not auth_manager.is_authenticated():
        st.warning("Veuillez vous connecter")
        st.session_state['page'] = 'login'
        st.rerun()
        return
    
    # Sidebar avec profil utilisateur
    with st.sidebar:
        st.subheader("👤 Profil")
        
        success, user_data = auth_manager.get_current_user()
        if success and user_data:
            st.markdown(format_user_display(user_data))
            
            if st.button("🚪 Déconnexion"):
                success, message = auth_manager.logout()
                if success:
                    st.success(message)
                    st.session_state['page'] = 'login'
                    st.rerun()
        else:
            st.error("Impossible de charger le profil")
            if st.button("🔄 Rafraîchir token"):
                success, msg = auth_manager.refresh_access_token()
                if success:
                    st.rerun()
                else:
                    st.error(msg)
    
    # Contenu principal de l'app
    st.title("Mon Application")
    # ... votre contenu ici ...
```

### 5. Simplifier `navigation.py`

#### Avant
```python
st.session_state['extra_input_params'] = {
    'Faculty':'text',
    'Year':'number',
    'Semester':'number',
}
# ... logique complexe ...
```

#### Après
```python
from auth import AuthManager

# Initialiser
init_session()
auth_manager = AuthManager()

# Navigation simplifiée
if auth_manager.is_authenticated():
    app_page()
else:
    if st.session_state['page'] == 'login':
        reset_session()
        login_page(guest_mode=True)
    elif st.session_state['page'] == 'signup':
        signup_page(confirmPass=True)
```

## 🎯 Avantages de la Migration

1. **✅ Plus de gestion PostgreSQL directe** - Tout passe par l'API
2. **✅ Validation standardisée** - Email et mot de passe validés
3. **✅ Gestion des tokens** - Automatique avec refresh
4. **✅ Meilleure sécurité** - Pas de hash de mot de passe côté client
5. **✅ Code plus propre** - Séparation des responsabilités
6. **✅ Testable** - Client API indépendant
7. **✅ Compatible avec le backend FastAPI** - Utilise les mêmes endpoints

## ⚠️ Notes Importantes

### Variables de Session

Le module utilise ces variables de session :
- `access_token` - Token JWT
- `refresh_token` - Token de rafraîchissement
- `user_data` - Données utilisateur
- `authenticated` - État d'authentification

Assurez-vous de ne pas les écraser dans votre code.

### OTP Email

L'API backend n'implémente pas encore l'OTP par email. Options :

1. **Désactiver temporairement** - Enregistrement direct sans OTP
2. **Implémenter côté backend** - Ajouter l'endpoint `/auth/verify-email`
3. **Garder pour les extras** - Utiliser OTP pour des fonctionnalités additionnelles

### Extra Input Params

Si vous avez des champs supplémentaires (Faculty, Year, etc.) :

```python
def signup_page_with_extras():
    auth_manager = AuthManager()
    
    # Champs standards
    email = st.text_input("Email")
    password = st.text_input("Password", type='password')
    
    # Champs supplémentaires
    faculty = st.text_input("Faculty")
    year = st.number_input("Year", step=1)
    
    if st.button("Register"):
        # 1. S'enregistrer d'abord
        success, message = auth_manager.register(email, email.split('@')[0], password)
        
        if success:
            # 2. Ensuite mettre à jour le profil avec les champs extras
            # TODO: Implémenter endpoint PATCH /users/me pour les extras
            st.success("Inscription réussie!")
```

## 🔧 Configuration

Éditez `auth/config.py` pour changer l'URL de l'API :

```python
# Pour développement local
BASE_URL = "http://localhost:8009"

# Pour production
# BASE_URL = "https://api.cryptobot.example.com"
```

## 📚 Documentation Complète

Voir `auth/README.md` pour :
- Guide d'utilisation complet
- Tous les endpoints disponibles
- Exemples de code
- Dépannage
