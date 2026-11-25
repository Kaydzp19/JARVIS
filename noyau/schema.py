"""
Structure de la base de chaque projet, au-delà de la marche 1.

installer(conn) est appelé à chaque ouverture d'une base : il ajoute ce
qui manque (tables, colonnes) sans jamais rien effacer. Ainsi un projet
créé avec une version plus ancienne de JARVIS se met à jour tout seul.
"""

TABLES = """
CREATE TABLE IF NOT EXISTS synapses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    note_source     INTEGER NOT NULL REFERENCES notes(id),
    note_cible      INTEGER NOT NULL REFERENCES notes(id),
    poids           REAL NOT NULL CHECK (poids >= 0 AND poids <= 1),
    activations     INTEGER NOT NULL DEFAULT 0,
    dernier_usage   TEXT,
    archivee        INTEGER NOT NULL DEFAULT 0 CHECK (archivee IN (0, 1)),
    oubli_calcule_jusqu_au TEXT NOT NULL,
    UNIQUE (note_source, note_cible)
);
CREATE TABLE IF NOT EXISTS usages_synapses (
    synapse_id  INTEGER NOT NULL REFERENCES synapses(id),
    jour        TEXT NOT NULL,
    UNIQUE (synapse_id, jour)
);
CREATE TABLE IF NOT EXISTS sommeils (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    debut     TEXT NOT NULL,
    statut    TEXT NOT NULL,
    appels_ia INTEGER NOT NULL DEFAULT 0,
    cout      REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reves (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    idee           TEXT NOT NULL,
    sources        TEXT NOT NULL,
    sources_titres TEXT NOT NULL,
    score          REAL NOT NULL,
    details        TEXT NOT NULL,
    statut         TEXT NOT NULL DEFAULT 'nouvelle'
                   CHECK (statut IN ('nouvelle', 'gardée', 'rejetée', 'creusée')),
    raison         TEXT,
    traite_le      TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    resume         TEXT NOT NULL,
    stats          TEXT NOT NULL,
    jetons_envoyes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS propositions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT NOT NULL,
    titre        TEXT NOT NULL,
    contenu      TEXT NOT NULL,
    liens        TEXT NOT NULL DEFAULT '[]',
    statut       TEXT NOT NULL DEFAULT 'en attente',
    creee_le     TEXT NOT NULL,
    acteur       TEXT NOT NULL,
    raison       TEXT,
    verification TEXT,
    traitee_le   TEXT,
    resultat_id  INTEGER
);
"""

COLONNES_AJOUTEES = {
    # table : [(colonne, définition)]
    "notes": [("validee", "INTEGER NOT NULL DEFAULT 0 CHECK (validee IN (0, 1))")],
    "taches": [("contrat", "TEXT"),
               # Planification (marche 7) : heure, durée, priorité, récurrence, rappel.
               ("heure", "TEXT"), ("duree", "INTEGER"),
               ("priorite", "TEXT NOT NULL DEFAULT 'normale'"),
               ("recurrence", "TEXT NOT NULL DEFAULT 'aucune'"),
               ("ancre", "TEXT"),            # première date d'une tâche récurrente
               ("rappel", "INTEGER"),        # minutes avant le début
               ("modifiee_le", "TEXT")],
    "propositions": [("note_cible", "INTEGER"),  # note visée par une modification
                     ("details", "TEXT")],      # précisions (JSON), ex. date et heure d'une tâche
}


# Recherche plein texte (FTS5, intégrée à SQLite) : titres + contenus des notes,
# sans tenir compte des accents ni des majuscules.
FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    titre, contenu, note_id UNINDEXED, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def fts_disponible(conn):
    """Vrai si la base sait faire de la recherche FTS5 (presque toujours le cas)."""
    try:
        conn.execute("SELECT 1 FROM notes_fts LIMIT 1")
        return True
    except Exception:
        return False


def installer(conn):
    conn.executescript(TABLES)
    try:
        conn.executescript(FTS)
    except Exception:
        pass  # SQLite sans FTS5 : la recherche simple prend le relais
    for table, colonnes in COLONNES_AJOUTEES.items():
        existantes = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for nom, definition in colonnes:
            if nom not in existantes:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {definition}")
    conn.commit()
