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
    "taches": [("contrat", "TEXT")],
    "propositions": [("note_cible", "INTEGER")],  # note visée par une modification
}


def installer(conn):
    conn.executescript(TABLES)
    for table, colonnes in COLONNES_AJOUTEES.items():
        existantes = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for nom, definition in colonnes:
            if nom not in existantes:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {definition}")
    conn.commit()
