"""Regression : mutation en place de UserSettings.api_keys (colonne JSON) doit persister
en base meme quand elle a lieu dans une session differente de celle qui a charge l'objet --
c'est le cas normal en production (chaque requete HTTP = nouvelle session DB).

Bug trouve le 2026-07-27 : sans flag_modified(), SQLAlchemy ne detecte pas une mutation en
place d'un dict sur une colonne JSON simple (pas de sqlalchemy.ext.mutable.MutableDict) --
la deuxieme paire de cles enregistree pour un utilisateur disparaissait silencieusement au
rechargement suivant. Corrige dans auth/models.py (set_api_credentials / set_active_mode /
remove_api_credentials appellent desormais flag_modified(self, "api_keys")).

Ce test utilise ses propres sessions SQLAlchemy independantes (pas la fixture partagee
db_session/patch_db_session de conftest.py, qui reutilise la meme Session pour tout le test
via la session-map d'identite -- ca masquerait justement ce bug, puisque l'objet Python
resterait le meme d'un appel a l'autre au lieu d'etre recharge depuis la base).
"""

from __future__ import annotations

import base64
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def encryption_key(monkeypatch):
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)
    return raw_key


@pytest.fixture
def session_factory(tmp_path, encryption_key):
    import auth.models  # noqa: F401
    from shared.models.base import Base

    db_path = tmp_path / "persistence_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _create_user_with_settings(Session, user_id: str) -> None:
    from auth.models import User, UserSettings

    session = Session()
    user = User(
        id=user_id,
        email=f"{user_id}@test.dev",
        username=user_id,
        hashed_password="x",  # noqa: S106
        first_name="Test",
        last_name="User",
    )
    settings = UserSettings(
        id=f"settings-{user_id}",
        user_id=user_id,
        theme="light",
        notification_preferences={},
        risk_profile="moderate",
        api_keys=None,
    )
    session.add_all([user, settings])
    session.commit()
    session.close()


def test_second_exchange_credentials_persist_across_separate_sessions(session_factory):
    """Reproduction exacte du bug : deux 'requetes' (= deux sessions) separees pour
    enregistrer Binance puis Kraken, verifie apres une TROISIEME session (fraiche) que
    les deux sont bien la."""
    from auth.models import UserSettings

    Session = session_factory
    _create_user_with_settings(Session, "user-1")

    # "Requete" 1 : enregistrer Binance (objet fraichement cree dans cette session -> marchait
    # deja avant le fix, pas le cas interessant)
    session1 = Session()
    settings1 = session1.query(UserSettings).filter_by(user_id="user-1").first()
    settings1.set_api_credentials("binance", "binance_key", "binance_secret")
    session1.commit()
    session1.close()

    # "Requete" 2 : enregistrer Kraken -- objet RECHARGE depuis la base, pas fraichement cree.
    # C'est exactement le cas qui etait casse sans flag_modified().
    session2 = Session()
    settings2 = session2.query(UserSettings).filter_by(user_id="user-1").first()
    settings2.set_api_credentials("kraken", "kraken_key", "kraken_secret")
    session2.commit()
    session2.close()

    # "Requete" 3 : verification fraiche, aucun objet en cache
    session3 = Session()
    settings3 = session3.query(UserSettings).filter_by(user_id="user-1").first()
    assert sorted(settings3.api_keys.keys()) == ["binance", "kraken"]
    assert settings3.get_api_key("binance") == "binance_key"
    assert settings3.get_api_key("kraken") == "kraken_key"
    session3.close()


def test_active_mode_switch_persists_across_separate_sessions(session_factory):
    from auth.models import UserSettings

    Session = session_factory
    _create_user_with_settings(Session, "user-2")

    session1 = Session()
    settings1 = session1.query(UserSettings).filter_by(user_id="user-2").first()
    settings1.set_api_credentials("binance", "live_key", "live_secret", mode="live")
    settings1.set_api_credentials("binance", "sandbox_key", "sandbox_secret", mode="sandbox")
    session1.commit()
    session1.close()

    session2 = Session()
    settings2 = session2.query(UserSettings).filter_by(user_id="user-2").first()
    settings2.set_active_mode("binance", "live")
    session2.commit()
    session2.close()

    session3 = Session()
    settings3 = session3.query(UserSettings).filter_by(user_id="user-2").first()
    assert settings3.get_active_mode("binance") == "live"
    assert settings3.get_api_key("binance") == "live_key"
    session3.close()
