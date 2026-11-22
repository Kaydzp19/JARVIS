"""
Synapses de JARVIS (marche 2) : le graphe vivant.

Une synapse est un lien pondéré entre deux notes d'un MÊME projet.
Elle naît d'un lien [[titre de note]] écrit dans une note.

- Son poids (entre 0 et 1) monte quand les deux notes servent ensemble.
- Il baisse un peu chaque nuit (l'oubli).
- Sous le seuil d'archivage, la synapse est archivée (mise de côté).

Règle de mise à jour, appliquée une fois par nuit :

    poids_nouveau = (1 - oubli) × poids_ancien
                    + apprentissage × (1 si les deux notes ont servi
                                       ensemble ce jour-là, sinon 0)

Garde-fou : seules les notes VALIDÉES peuvent renforcer une synapse,
pour qu'une erreur (par exemple de l'IA) ne se renforce pas toute seule.

Toutes les fonctions reçoivent la date en paramètre : rien n'utilise
l'horloge de l'ordinateur, ce qui permet de simuler des nuits en test.

Uniquement la bibliothèque standard de Python. Aucune logique de domaine.
"""

from datetime import date as _date, timedelta

from noyau import projets, schema

# ------------------------------------------------------------------
# Réglages : le SEUL endroit où changer ces valeurs.
# ------------------------------------------------------------------
REGLAGES = {
    "poids_initial": 0.10,      # poids d'une synapse à sa création
    "apprentissage": 0.10,      # gain quand deux notes servent ensemble
    "oubli": 0.02,              # part du poids perdue chaque nuit (2 %)
    "plafond": 1.0,             # poids maximum
    "seuil_archivage": 0.05,    # sous ce poids, la synapse est archivée
}

ACTEUR_PAR_DEFAUT = "jarvis"

# La structure des tables est dans noyau/schema.py.



# ------------------------------------------------------------------
# Outils internes
# ------------------------------------------------------------------

def _jour(d):
    """Accepte une date Python ou un texte 'AAAA-MM-JJ'. Renvoie une date."""
    if isinstance(d, _date):
        return d
    return _date.fromisoformat(str(d)[:10])


def _reglages(surcharge):
    r = dict(REGLAGES)
    if surcharge:
        r.update(surcharge)
    return r


def _installer(conn):
    """Ajoute à la base d'un projet ce dont la marche 2 a besoin (sans rien casser)."""
    schema.installer(conn)


def _ouvrir(projet, racine):
    conn = projets._connexion(projet, racine)
    _installer(conn)
    return conn


def _journal(conn, jour, evenement, acteur, raison):
    conn.execute(
        "INSERT INTO journal (date, acteur, evenement, raison) VALUES (?, ?, ?, ?)",
        (_jour(jour).isoformat(), acteur, evenement, raison),
    )


# ------------------------------------------------------------------
# Validation des notes (garde-fou)
# ------------------------------------------------------------------

def valider_note(projet, note_id, date, racine=None, acteur=ACTEUR_PAR_DEFAUT,
                 raison=None):
    """Marque une note comme validée : elle peut désormais renforcer des synapses."""
    conn = _ouvrir(projet, racine)
    try:
        with conn:
            cur = conn.execute("UPDATE notes SET validee = 1 WHERE id = ?", (note_id,))
            if cur.rowcount == 0:
                raise KeyError(f"Aucune note {note_id} dans le projet {projet!r}.")
            _journal(conn, date, f"note validée : {note_id}", acteur, raison)
    finally:
        conn.close()


def note_validee(projet, note_id, racine=None):
    conn = _ouvrir(projet, racine)
    try:
        ligne = conn.execute("SELECT validee FROM notes WHERE id = ?", (note_id,)).fetchone()
        return bool(ligne and ligne["validee"])
    finally:
        conn.close()


# ------------------------------------------------------------------
# Création des synapses à partir des liens [[...]]
# ------------------------------------------------------------------

def creer_synapses_de_note(projet, note_id, date, racine=None, reglages=None,
                           acteur=ACTEUR_PAR_DEFAUT):
    """
    Lit les liens [[titre]] de la note et crée une synapse vers chaque note
    du MÊME projet qui porte ce titre. Un lien vers un titre inconnu dans
    ce projet est ignoré : une synapse ne traverse jamais deux projets.
    Renvoie la liste des identifiants des synapses créées.
    """
    r = _reglages(reglages)
    titres = projets.liens_de_note(projet, note_id, racine)
    jour = _jour(date).isoformat()
    crees = []
    conn = _ouvrir(projet, racine)
    try:
        with conn:
            for titre in titres:
                cibles = conn.execute(
                    "SELECT id FROM notes WHERE titre = ? AND id != ? ORDER BY id",
                    (titre, note_id)).fetchall()
                for cible in cibles:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO synapses "
                        "(note_source, note_cible, poids, oubli_calcule_jusqu_au) "
                        "VALUES (?, ?, ?, ?)",
                        (note_id, cible["id"], r["poids_initial"], jour))
                    if cur.rowcount:
                        crees.append(cur.lastrowid)
                        _journal(conn, date,
                                 f"synapse créée : {note_id} → {cible['id']}",
                                 acteur, f"lien [[{titre}]]")
        return crees
    finally:
        conn.close()


def creer_synapses_entrantes(projet, note_id, date, racine=None, reglages=None,
                             acteur=ACTEUR_PAR_DEFAUT):
    """
    Crée les synapses venant des notes qui citaient DÉJÀ cette note avec
    [[son titre]] avant qu'elle existe. Sans cela, un lien écrit vers une
    note future serait perdu. Renvoie la liste des synapses créées.
    """
    r = _reglages(reglages)
    jour = _jour(date).isoformat()
    notes = projets.lister_notes(projet, racine)
    titre = next((n["titre"] for n in notes if n["id"] == note_id), None)
    if titre is None:
        raise KeyError(f"Aucune note {note_id} dans le projet {projet!r}.")
    crees = []
    conn = _ouvrir(projet, racine)
    try:
        with conn:
            for n in notes:
                if n["id"] == note_id:
                    continue
                if titre not in projets.trouver_liens(projets.lire_note(projet, n["id"], racine)):
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO synapses "
                    "(note_source, note_cible, poids, oubli_calcule_jusqu_au) VALUES (?, ?, ?, ?)",
                    (n["id"], note_id, r["poids_initial"], jour))
                if cur.rowcount:
                    crees.append(cur.lastrowid)
                    _journal(conn, date, f"synapse créée : {n['id']} → {note_id}", acteur,
                             f"lien [[{titre}]] écrit avant la note")
        return crees
    finally:
        conn.close()


def creer_synapse(projet, note_a, note_b, date, racine=None, reglages=None,
                  acteur=ACTEUR_PAR_DEFAUT, raison=None):
    """
    Crée une synapse a → b sans lien [[...]] écrit (par exemple quand Kayd garde
    une idée rêvée). Seulement entre deux notes VALIDÉES du même projet.
    Renvoie l'id de la synapse créée, ou None (déjà liée, ou note non validée).
    """
    r = _reglages(reglages)
    conn = _ouvrir(projet, racine)
    try:
        validees = {x["id"] for x in conn.execute(
            "SELECT id FROM notes WHERE id IN (?, ?) AND validee = 1", (note_a, note_b))}
        if note_a == note_b or validees != {note_a, note_b}:
            return None
        existe = conn.execute(
            "SELECT 1 FROM synapses WHERE (note_source = ? AND note_cible = ?) "
            "OR (note_source = ? AND note_cible = ?)", (note_a, note_b, note_b, note_a)).fetchone()
        if existe:
            return None
        with conn:
            cur = conn.execute(
                "INSERT INTO synapses (note_source, note_cible, poids, oubli_calcule_jusqu_au) "
                "VALUES (?, ?, ?, ?)", (note_a, note_b, r["poids_initial"], _jour(date).isoformat()))
            _journal(conn, date, f"synapse créée : {note_a} → {note_b}", acteur, raison)
            return cur.lastrowid
    finally:
        conn.close()


def relier_note(projet, note_id, date, racine=None, reglages=None, acteur=ACTEUR_PAR_DEFAUT):
    """Liens sortants ([[...]] de la note) + liens entrants (notes qui la citaient)."""
    return (creer_synapses_de_note(projet, note_id, date, racine, reglages, acteur)
            + creer_synapses_entrantes(projet, note_id, date, racine, reglages, acteur))


# ------------------------------------------------------------------
# Usage ensemble (renforcement)
# ------------------------------------------------------------------

def utiliser_ensemble(projet, note_a, note_b, date, racine=None,
                      acteur=ACTEUR_PAR_DEFAUT, raison=None):
    """
    Signale que deux notes ont servi ensemble ce jour-là.
    Si les DEUX notes sont validées, les synapses entre elles (dans un sens
    ou dans l'autre) comptent une activation ; le gain d'apprentissage est
    appliqué lors de la nuit suivante (voir appliquer_oubli).
    Renvoie True si au moins une synapse a été activée, sinon False.
    """
    jour = _jour(date).isoformat()
    conn = _ouvrir(projet, racine)
    try:
        with conn:
            validees = {r["id"] for r in conn.execute(
                "SELECT id FROM notes WHERE id IN (?, ?) AND validee = 1",
                (note_a, note_b))}
            if validees != {note_a, note_b}:
                _journal(conn, date,
                         f"renforcement refusé : {note_a} ↔ {note_b}",
                         acteur, "note non validée")
                return False
            synapses = conn.execute(
                "SELECT id FROM synapses WHERE archivee = 0 AND "
                "((note_source = ? AND note_cible = ?) OR "
                " (note_source = ? AND note_cible = ?))",
                (note_a, note_b, note_b, note_a)).fetchall()
            for s in synapses:
                conn.execute(
                    "INSERT OR IGNORE INTO usages_synapses (synapse_id, jour) VALUES (?, ?)",
                    (s["id"], jour))
                conn.execute(
                    "UPDATE synapses SET activations = activations + 1, dernier_usage = ? "
                    "WHERE id = ?", (jour, s["id"]))
            return bool(synapses)
    finally:
        conn.close()


# ------------------------------------------------------------------
# Oubli quotidien (et application du renforcement)
# ------------------------------------------------------------------

def appliquer_oubli(projet, date, racine=None, reglages=None,
                    acteur=ACTEUR_PAR_DEFAUT):
    """
    Calcule toutes les nuits écoulées jusqu'à « date » pour chaque synapse
    active du projet, avec la formule du haut de ce fichier.
    Archive toute synapse passée sous le seuil d'archivage.
    Renvoie un petit bilan : {"renforcees": n, "archivees": n}.
    """
    r = _reglages(reglages)
    fin = _jour(date)
    bilan = {"renforcees": 0, "archivees": 0}
    conn = _ouvrir(projet, racine)
    try:
        with conn:
            for s in conn.execute("SELECT * FROM synapses WHERE archivee = 0").fetchall():
                jour = _jour(s["oubli_calcule_jusqu_au"])
                if jour >= fin:
                    continue
                usages = {u["jour"] for u in conn.execute(
                    "SELECT jour FROM usages_synapses WHERE synapse_id = ?", (s["id"],))}
                poids = s["poids"]
                archivee = 0
                while jour < fin:
                    # Nuit entre « jour » et « jour + 1 ».
                    servi = 1 if jour.isoformat() in usages else 0
                    ancien = poids
                    poids = (1 - r["oubli"]) * poids + r["apprentissage"] * servi
                    poids = max(0.0, min(r["plafond"], poids))
                    jour += timedelta(days=1)
                    if servi:
                        bilan["renforcees"] += 1
                        _journal(conn, jour,
                                 f"synapse renforcée : {s['note_source']} → {s['note_cible']} "
                                 f"({ancien:.3f} → {poids:.3f})",
                                 acteur, "notes utilisées ensemble")
                    if poids < r["seuil_archivage"]:
                        archivee = 1
                        bilan["archivees"] += 1
                        _journal(conn, jour,
                                 f"synapse archivée : {s['note_source']} → {s['note_cible']} "
                                 f"(poids {poids:.3f})",
                                 acteur, f"poids sous le seuil {r['seuil_archivage']}")
                        break
                conn.execute(
                    "UPDATE synapses SET poids = ?, archivee = ?, oubli_calcule_jusqu_au = ? "
                    "WHERE id = ?", (poids, archivee, jour.isoformat(), s["id"]))
        return bilan
    finally:
        conn.close()


# ------------------------------------------------------------------
# Lecture
# ------------------------------------------------------------------

def lister_synapses(projet, racine=None, avec_archivees=True):
    conn = _ouvrir(projet, racine)
    try:
        sql = "SELECT * FROM synapses"
        if not avec_archivees:
            sql += " WHERE archivee = 0"
        return [dict(r) for r in conn.execute(sql + " ORDER BY id")]
    finally:
        conn.close()


def synapse_entre(projet, note_a, note_b, racine=None):
    """Renvoie la synapse note_a → note_b (ou None)."""
    conn = _ouvrir(projet, racine)
    try:
        r = conn.execute(
            "SELECT * FROM synapses WHERE note_source = ? AND note_cible = ?",
            (note_a, note_b)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()
