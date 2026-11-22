"""
Lecture des réglages de JARVIS.

Ordre de priorité (le premier trouvé gagne) :
  1. variables d'environnement (ex. DOSSIER_DONNEES=...) ;
  2. fichier reglages.local (à la racine du dépôt, ou chemin donné par
     la variable JARVIS_REGLAGES) — jamais envoyé sur GitHub ;
  3. valeurs par défaut ci-dessous.

Les secrets (clés API) ne sont lus QUE depuis reglages.local ou
l'environnement. Ils ne sont jamais écrits dans le journal.
"""

import os
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent

DEFAUTS = {
    "DOSSIER_DONNEES": "~/.jarvis",
    "BUDGET_IA_MAX_EUR_MOIS": "5",
    "CLE_API_GEMINI": "",
    "CLE_API_ANTHROPIC": "",
    "COCKPIT_JETON": "",
}


def chemin_fichier():
    return Path(os.environ.get("JARVIS_REGLAGES", RACINE_DEPOT / "reglages.local"))


def _lire_fichier(chemin):
    valeurs = {}
    try:
        lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, NotADirectoryError):
        return valeurs
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def lire(cle, defaut=None):
    if os.environ.get(cle):
        return os.environ[cle]
    fichier = _lire_fichier(chemin_fichier())
    if fichier.get(cle):
        return fichier[cle]
    if defaut is not None:
        return defaut
    return DEFAUTS.get(cle, "")


def dossier_donnees():
    return Path(os.path.expanduser(lire("DOSSIER_DONNEES")))
