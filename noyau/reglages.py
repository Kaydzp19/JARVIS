"""
Lecture des réglages de JARVIS.

Où vivent les réglages : dans ~/.jarvis/reglages.local, HORS du dépôt.
Ce fichier est créé automatiquement, avec les valeurs par défaut, la première
fois qu'une commande JARVIS est lancée. Tu peux ensuite le modifier.

Ordre de priorité (le premier trouvé gagne) :
  1. variables d'environnement (ex. DOSSIER_DONNEES=...) ;
  2. ~/.jarvis/reglages.local (dans le dossier de données) ;
  3. reglages.local à la racine du dépôt (ancienne place, toujours lue ;
     ou chemin donné par la variable JARVIS_REGLAGES) ;
  4. valeurs par défaut ci-dessous.

Les secrets (clés API) ne sont lus QUE depuis ces fichiers ou l'environnement.
Ils ne sont jamais écrits dans le journal.
"""

import os
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent
NOM_FICHIER = "reglages.local"

DEFAUTS = {
    "DOSSIER_DONNEES": "~/.jarvis",
    "BUDGET_IA_MAX_EUR_MOIS": "5",
    "CLE_API_GEMINI": "",
    "CLE_API_ANTHROPIC": "",
    "COCKPIT_JETON": "",
    # --- Routeur IA ---
    "mode_ia": "simule",              # simule (sans clé) ou reel
    "modele_gemini": "gemini-2.5-flash",
    "gemini_url": "https://generativelanguage.googleapis.com",
    "modele_claude": "claude-opus-5-5",
    "effort_claude": "medium",
    "anthropic_url": "https://api.anthropic.com",
    # --- Sommeil et rêve (marche 6) ---
    "idees_par_projet": "1",          # idées gardées par projet et par nuit
    "candidates_par_nuit": "5",       # idées imaginées par l'IA créative
    "cloud_pour_reveil": "false",     # cloud payant permis pour la phase réveil ?
    "modele_local": "aucun",          # nom du modèle Ollama, ex. llama3.2 (plus tard)
    "ollama_url": "http://127.0.0.1:11434",
    "tokens_max_analyse": "1500",     # jetons envoyés au maximum pour le résumé
    "tri_peremption_jours": "90",     # note « à revoir » après ce nombre de jours
    # --- Tes contraintes, lues par la phase réveil ---
    "contrainte_budget_eur": "0",
    "contrainte_niveau": "débutant",
    "contrainte_objectifs": "",
}

# Contenu du fichier créé automatiquement dans ~/.jarvis/ (aucun secret, aucune donnée perso).
MODELE_FICHIER = """# Réglages de JARVIS — ce fichier est à toi, il n'est jamais envoyé sur GitHub.
# Une ligne = un réglage : nom=valeur. Les lignes qui commencent par # sont ignorées.

# --- IA ---
# simule = IA simulée, sans clé ni Internet (par défaut). reel = vraies IA.
mode_ia=simule
# Budget maximum pour l'IA payante, en euros par mois.
BUDGET_IA_MAX_EUR_MOIS=5

# --- Sommeil et rêve ---
# Nombre d'idées gardées par projet et par nuit.
idees_par_projet=1
# Nombre d'idées candidates imaginées par l'IA créative chaque nuit.
candidates_par_nuit=5
# true = la phase réveil peut utiliser le cloud payant (Claude), dans la limite
# du budget IA mensuel. false = jamais de cloud payant pour le rêve.
cloud_pour_reveil=false
# Modèle local Ollama (ex. llama3.2). « aucun » tant qu'Ollama n'est pas installé.
modele_local=aucun
# Nombre maximum de jetons envoyés pour le résumé de nuit (1 jeton ≈ 4 caractères).
tokens_max_analyse=1500
# Une note non modifiée depuis ce nombre de jours est proposée « à revoir ».
tri_peremption_jours=90

# --- Tes contraintes (utilisées pour noter les idées du rêve) ---
# Budget disponible pour une idée, en euros.
contrainte_budget_eur=0
# Ton niveau : débutant, intermédiaire ou avancé.
contrainte_niveau=débutant
# Tes objectifs, en quelques mots séparés par des virgules.
contrainte_objectifs=

# --- Clés API (facultatif ; à remplir toi-même, jamais dans le chat) ---
# CLE_API_GEMINI=
# CLE_API_ANTHROPIC=
"""


def chemin_fichier():
    """Ancienne place : reglages.local à la racine du dépôt (ou JARVIS_REGLAGES)."""
    return Path(os.environ.get("JARVIS_REGLAGES", RACINE_DEPOT / NOM_FICHIER))


def _lire_fichier(chemin):
    valeurs = {}
    try:
        lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return valeurs
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def dossier_donnees():
    """Le dossier de données (~/.jarvis). Lu sans le fichier qui s'y trouve."""
    valeur = (os.environ.get("DOSSIER_DONNEES")
              or _lire_fichier(chemin_fichier()).get("DOSSIER_DONNEES")
              or DEFAUTS["DOSSIER_DONNEES"])
    return Path(os.path.expanduser(valeur))


def fichier_donnees():
    """~/.jarvis/reglages.local : la place principale des réglages."""
    return dossier_donnees() / NOM_FICHIER


def creer_fichier_si_absent():
    """Crée ~/.jarvis/reglages.local avec les valeurs par défaut s'il n'existe pas."""
    f = fichier_donnees()
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(MODELE_FICHIER, encoding="utf-8")
        try:
            f.chmod(0o600)  # lisible par toi seul
        except OSError:
            pass
    return f


def lire(cle, defaut=None):
    if os.environ.get(cle):
        return os.environ[cle]
    for chemin in (fichier_donnees(), chemin_fichier()):
        valeur = _lire_fichier(chemin).get(cle)
        if valeur:
            return valeur
    if defaut is not None:
        return defaut
    return DEFAUTS.get(cle, "")


def lire_nombre(cle, defaut):
    """Lit un réglage numérique (accepte la virgule française)."""
    try:
        return float(str(lire(cle)).replace(",", "."))
    except ValueError:
        return defaut


def lire_booleen(cle):
    """true / oui / 1 = vrai ; tout le reste = faux."""
    return str(lire(cle)).strip().lower() in ("true", "vrai", "oui", "yes", "1")
