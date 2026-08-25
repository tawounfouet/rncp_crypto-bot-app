# Politique de confidentialité — Crypto Bot (placeholder)

> **Note :** ce document est un **placeholder volontairement minimal** pour la soutenance.
> Il ne constitue pas un texte juridique définitif et doit être affiné et validé
> (DPO / juriste) avant une mise en production réelle.

Dernière mise à jour : 2026-08-07

Cette politique décrit, de manière simplifiée, comment l'application Crypto Bot
collecte, utilise, conserve et protège les données personnelles des utilisateurs.

## Responsable du traitement
Le responsable du traitement est l'équipe de développement du projet Crypto Bot.

## Données collectées
- Données d'inscription : prénom, nom, adresse email, nom d'utilisateur, mot de passe (haché).
- Clés API exchange (ex. Binance) : stockées **chiffrées** (AES) si l'utilisateur les renseigne.
- Données d'usage : logs anonymisés, préférences d'affichage (thème), données mockées du mode démo.

## Finalités du traitement
- Authentification et gestion du compte.
- Exécution des ordres et suivi du portefeuille via les exchanges configurés.
- Sécurité du service et prévention des usages non autorisés.

## Base légale
- Exécution du contrat / fourniture du service : gestion du compte et des ordres.
- **Consentement explicite** : requis à l'inscription via la case à cocher dédiée.

## Durée de conservation
- Les données sont conservées tant que le compte est actif.
- Les comptes inactifs sont **purgeés automatiquement après 730 jours**
  (job `purge_inactive_users.py`).

## Droits des personnes
Conformément au RGPD, vous disposez des droits d'**accès, rectification, effacement,
limitation, opposition et portabilité** de vos données.

Pour exercer ces droits (export ou suppression de vos données), utilisez la page
**Gestion de compte** de l'application ou contactez l'équipe projet.

## Sécurité
- Mots de passe hachés, clés API chiffrées, contrôle d'accès et journalisation des accès sensibles.

## Transfert de données
- Aucun transfert international n'est effectué par défaut.

## Contact
Pour toute question relative à la confidentialité des données, contactez l'équipe projet.

---

_Politique fournie à titre indicatif pour l'application mock-first. À affiner avant mise en production réelle._
