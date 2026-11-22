"""
Projets étanches de JARVIS (marche 1).

Chaque projet a son propre dossier et sa propre base de données :

    <racine>/projets/<nom>/
        projet.db      base SQLite du projet (notes, taches, journal)
        notes/         les notes, une par fichier Markdown (.md)

« Étanche » veut dire qu'un projet ne voit jamais les données d'un autre :
chaque fonction ouvre uniquement la base du projet qu'on lui donne.

La racine par défaut est ~/.jarvis (ou la valeur de DOSSIER_DONNEES).
Elle n'est jamais dans le dépôt Git : ce sont des données personnelles.

Ce fichier n'utilise que la bibliothèque standard de Python.
Il ne contient rien de propre à un domaine (crypto, agenda, sport...).
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from noyau import reglages, schema

# Acteur noté dans le journal quand rien d'autre n'est précisé.
ACTEUR_PAR_DEFAUT = "jarvis"

# Repère les liens du type [[titre de note]].
MOTIF_LIEN = re.compile(r"\[\[([^\[\]]+)\]\]")

# Structure de la base de chaque projet.
SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    titre      TEXT NOT NULL,
    chemin     TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'note',
    creee_le   TEXT NOT NULL,
    modifiee_le TEXT NOT NULL,
    sensible   INTEGER NOT NULL DEFAULT 0 CHECK (sensible IN (0, 1))
);
CREATE TABLE IF NOT EXISTS taches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    titre      TEXT NOT NULL,
    statut     TEXT NOT NULL DEFAULT 'à faire',
    echeance   TEXT,
    note_id    INTEGER REFERENCES notes(id)
);
CREATE TABLE IF NOT EXISTS journal (
    date       TEXT NOT NULL,
    acteur     TEXT NOT NULL,
    evenement  TEXT NOT NULL,
    raison     TEXT
);
"""


# ------------------------------------------------------------------
# Outils internes
# ------------------------------------------------------------------

def _maintenant():
    return datetime.now().isoformat(timespec="seconds")


def racine_par_defaut():
    """Dossier des données : DOSSIER_DONNEES (environnement ou reglages.local), sinon ~/.jarvis."""
    return reglages.dossier_donnees()


def _verifier_nom(nom):
    """Refuse les noms vides ou qui pourraient sortir du dossier projets."""
    if not nom or nom in (".", "..") or "/" in nom or "\\" in nom or nom.startswith("."):
        raise ValueError(f"Nom de projet invalide : {nom!r}")
    return nom


def dossier_projet(nom, racine=None):
    racine = Path(racine) if racine else racine_par_defaut()
    return racine / "projets" / _verifier_nom(nom)


def _connexion(nom, racine=None):
    """Ouvre la base d'un projet existant (et seulement celle-là)."""
    chemin_db = dossier_projet(nom, racine) / "projet.db"
    if not chemin_db.exists():
        raise FileNotFoundError(f"Le projet {nom!r} n'existe pas.")
    conn = sqlite3.connect(chemin_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema.installer(conn)  # ajoute les tables des marches suivantes si besoin
    return conn


def _ecrire_journal(conn, evenement, acteur=ACTEUR_PAR_DEFAUT, raison=None):
    conn.execute(
        "INSERT INTO journal (date, acteur, evenement, raison) VALUES (?, ?, ?, ?)",
        (_maintenant(), acteur, evenement, raison),
    )


def _nom_de_fichier(titre):
    """Transforme un titre en nom de fichier simple et sûr."""
    nom = re.sub(r"[^\w\- ]", "", titre, flags=re.UNICODE).strip().replace(" ", "-")
    return nom or "note"


# ------------------------------------------------------------------
# Projets
# ------------------------------------------------------------------

def creer_projet(nom, racine=None, acteur=ACTEUR_PAR_DEFAUT, raison=None):
    """Crée le dossier du projet, son dossier notes/ et sa base projet.db."""
    dossier = dossier_projet(nom, racine)
    if (dossier / "projet.db").exists():
        raise FileExistsError(f"Le projet {nom!r} existe déjà.")
    (dossier / "notes").mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(dossier / "projet.db") as conn:
        conn.executescript(SCHEMA)
        schema.installer(conn)
        _ecrire_journal(conn, f"projet créé : {nom}", acteur, raison)
    conn.close()
    return dossier


def lister_projets(racine=None):
    racine = Path(racine) if racine else racine_par_defaut()
    dossier = racine / "projets"
    if not dossier.exists():
        return []
    return sorted(p.name for p in dossier.iterdir() if (p / "projet.db").exists())


# ------------------------------------------------------------------
# Notes
# ------------------------------------------------------------------

def creer_note(projet, titre, contenu="", type_note="note", sensible=False,
               racine=None, acteur=ACTEUR_PAR_DEFAUT, raison=None, validee=False,
               horodatage=None):
    """Écrit un fichier .md dans notes/ et ajoute une ligne dans la table notes."""
    dossier_notes = dossier_projet(projet, racine) / "notes"
    base = _nom_de_fichier(titre)
    fichier = dossier_notes / f"{base}.md"
    n = 2
    while fichier.exists():  # évite d'écraser une note existante
        fichier = dossier_notes / f"{base}-{n}.md"
        n += 1

    conn = _connexion(projet, racine)
    try:
        fichier.write_text(contenu, encoding="utf-8")
        maintenant = horodatage or _maintenant()  # horodatage : pour la démo et les tests
        with conn:
            cur = conn.execute(
                "INSERT INTO notes (titre, chemin, type, creee_le, modifiee_le, sensible, validee) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (titre, f"notes/{fichier.name}", type_note, maintenant, maintenant,
                 1 if sensible else 0, 1 if validee else 0),
            )
            _ecrire_journal(conn, f"note créée : {titre}", acteur, raison)
        return cur.lastrowid
    finally:
        conn.close()


def modifier_note(projet, note_id, contenu, racine=None, acteur=ACTEUR_PAR_DEFAUT,
                  raison=None):
    """Remplace le texte d'une note (fichier .md) et met à jour « modifiée le »."""
    conn = _connexion(projet, racine)
    try:
        ligne = conn.execute("SELECT chemin, titre FROM notes WHERE id = ?",
                             (note_id,)).fetchone()
        if ligne is None:
            raise KeyError(f"Aucune note {note_id} dans le projet {projet!r}.")
        (dossier_projet(projet, racine) / ligne["chemin"]).write_text(contenu, encoding="utf-8")
        with conn:
            conn.execute("UPDATE notes SET modifiee_le = ? WHERE id = ?",
                         (_maintenant(), note_id))
            _ecrire_journal(conn, f"note modifiée : {ligne['titre']}", acteur, raison)
    finally:
        conn.close()


def lister_notes(projet, racine=None):
    conn = _connexion(projet, racine)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM notes ORDER BY id")]
    finally:
        conn.close()


def lire_note(projet, note_id, racine=None):
    """Renvoie le contenu du fichier Markdown d'une note de CE projet."""
    conn = _connexion(projet, racine)
    try:
        ligne = conn.execute("SELECT chemin FROM notes WHERE id = ?", (note_id,)).fetchone()
    finally:
        conn.close()
    if ligne is None:
        raise KeyError(f"Aucune note {note_id} dans le projet {projet!r}.")
    return (dossier_projet(projet, racine) / ligne["chemin"]).read_text(encoding="utf-8")


def trouver_liens(texte):
    """Repère les liens [[titre de note]] dans un texte. Renvoie les titres, sans doublon."""
    vus = []
    for titre in MOTIF_LIEN.findall(texte):
        titre = titre.strip()
        if titre and titre not in vus:
            vus.append(titre)
    return vus


def liens_de_note(projet, note_id, racine=None):
    return trouver_liens(lire_note(projet, note_id, racine))


# ------------------------------------------------------------------
# Tâches
# ------------------------------------------------------------------

def creer_tache(projet, titre, statut="à faire", echeance=None, note_id=None,
                racine=None, acteur=ACTEUR_PAR_DEFAUT, raison=None):
    conn = _connexion(projet, racine)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO taches (titre, statut, echeance, note_id) VALUES (?, ?, ?, ?)",
                (titre, statut, echeance, note_id),
            )
            _ecrire_journal(conn, f"tâche créée : {titre}", acteur, raison)
        return cur.lastrowid
    finally:
        conn.close()


def lister_taches(projet, racine=None):
    conn = _connexion(projet, racine)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM taches ORDER BY id")]
    finally:
        conn.close()


# ------------------------------------------------------------------
# Journal
# ------------------------------------------------------------------

def lire_journal(projet, racine=None):
    conn = _connexion(projet, racine)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM journal ORDER BY rowid")]
    finally:
        conn.close()
