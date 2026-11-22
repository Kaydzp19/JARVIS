"""
Base « système » de JARVIS : ~/.jarvis/systeme.db

Elle contient ce qui n'appartient à aucun projet :
- budget_ia : le montant estimé dépensé en IA, par mois (plafond global) ;
- appels_ia : le détail de chaque appel à l'IA (sans le texte envoyé) ;
- modules   : quels modules sont actifs, et dans quel mode.
Elle ne contient jamais de notes ni de secrets.
"""

import sqlite3

from noyau import reglages

SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_ia (
    mois           TEXT PRIMARY KEY,
    montant_estime REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS appels_ia (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    fournisseur TEXT NOT NULL,
    tache       TEXT NOT NULL,
    difficulte  TEXT NOT NULL,
    sensible    INTEGER NOT NULL,
    cout_estime REAL NOT NULL,
    statut      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS modules (
    nom   TEXT PRIMARY KEY,
    actif INTEGER NOT NULL DEFAULT 0,
    mode  TEXT NOT NULL DEFAULT 'DEMO'
);
"""


def connexion(racine=None):
    dossier = racine if racine is not None else reglages.dossier_donnees()
    from pathlib import Path
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(dossier / "systeme.db")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
