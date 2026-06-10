#!/usr/bin/env python3
"""Générateur de fichiers de requirements à partir de versions.env.

Ce script lit les variables définies dans versions.env et remplace les
placeholders ($VAR ou ${VAR}) dans tous les fichiers *.template du projet.
"""

import os
import re
import sys
from pathlib import Path

# Chemin de la racine de l'application
APP_ROOT = Path(__file__).resolve().parent.parent


def load_env_vars(env_file_path: Path) -> dict[str, str]:
    """Charge les variables d'un fichier .env/env dans un dict."""
    variables = {}
    if not env_file_path.exists():
        print(f"Erreur : Le fichier de configuration {env_file_path} n'existe pas.")
        sys.exit(1)

    # Lire le fichier ligne par ligne
    with open(env_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Ignorer les commentaires et lignes vides
            if not line or line.startswith("#"):
                continue
            # Gérer le format VAR=VAL
            if "=" in line:
                key, val = line.split("=", 1)
                variables[key.strip()] = val.strip()

    return variables


def generate_from_template(template_path: Path, variables: dict[str, str]) -> None:
    """Remplace les variables dans le template et écrit le fichier final."""
    output_path = template_path.with_suffix("")  # Retire le .template
    
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Fonction de remplacement pour re.sub
    def replacer(match):
        var_name = match.group(1) or match.group(2)
        # Tenter de récupérer depuis versions.env, sinon depuis l'environnement système
        val = variables.get(var_name) or os.environ.get(var_name)
        if val is None:
            print(f"Avertissement : Variable {var_name} non définie dans versions.env ni dans l'environnement.")
            return match.group(0)  # Laisser tel quel
        return val

    # Regex pour matcher $VAR ou ${VAR}
    pattern = re.compile(r"\$(?:([a-zA-Z0-9_]+)|\{([a-zA-Z0-9_]+)\})")
    new_content = pattern.sub(replacer, content)

    # Écriture du fichier généré
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✓ Généré : {output_path.relative_to(APP_ROOT)}")


def main():
    versions_file = APP_ROOT / "versions.env"
    variables = load_env_vars(versions_file)
    
    # Trouver tous les fichiers .template dans le projet
    templates_found = list(APP_ROOT.glob("**/*.template"))
    if not templates_found:
        print("Aucun fichier *.template trouvé.")
        return

    for template in templates_found:
        generate_from_template(template, variables)


if __name__ == "__main__":
    main()
