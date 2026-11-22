"""
Corps calleux de JARVIS (marche 3) : le canal UNIQUE entre les deux hémisphères.

L'hémisphère actif (Claude, orchestrateur, agents, modules) ne lit et
n'écrit la mémoire que par ces fonctions.

Les 4 messages du contrat :
    se_souvenir(projet, requete, limite)   lit, n'écrit rien
    proposer(projet, type, contenu, liens) crée une proposition EN ATTENTE, sur copie
    activer(projet, ids_notes)             renforce les synapses entre notes utilisées ensemble
    journal(projet, evenement, raison)     ajoute une ligne au journal

Actions HUMAINES (Kayd, via le cockpit ou la ligne de commande), jamais
appelées par un agent :
    valider_proposition, refuser_proposition, creer_note_humaine,
    modifier_note_humaine, terminer_tache

Fonctions internes réservées à l'orchestrateur (lecture de l'état) :
    lister_projets, etat_projet, lire_proposition, annoter_verification,
    enregistrer_contrat
"""

import json
import re
import sqlite3
from itertools import combinations

from noyau import projets, synapses
from noyau.outils import jour, mots_cles, normaliser

# Types de propositions acceptés. Rien ne permet de publier, payer ou
# supprimer : ces actions ne peuvent pas être proposées par un agent.
TYPES_PROPOSITION = ("note", "synthese", "tache", "modification")
STATUTS = ("en attente", "écrite", "refusée")
MASQUE_SENSIBLE = "[note sensible : contenu masqué]"


def _date_texte(date):
    return jour(date).isoformat()


def _journal_brut(conn, date, acteur, evenement, raison):
    conn.execute(
        "INSERT INTO journal (date, acteur, evenement, raison) VALUES (?, ?, ?, ?)",
        (_date_texte(date), acteur, evenement, raison))


# ==================================================================
# 1. se_souvenir : lire la mémoire (n'écrit rien)
# ==================================================================

def _extrait(texte, mots, taille=240):
    if not texte:
        return ""
    norm = normaliser(texte)
    debut = 0
    for m in mots:
        i = norm.find(m)
        if i >= 0:
            debut = max(0, i - 60)
            break
    morceau = texte[debut:debut + taille].strip().replace("\n", " ")
    return ("…" if debut else "") + morceau + ("…" if debut + taille < len(texte) else "")


def se_souvenir(projet, requete="", limite=5, racine=None, masquer_sensibles=False):
    """
    Renvoie les notes pertinentes du projet : [{id, titre, extrait, poids,
    pertinence, sensible, validee}], triées par pertinence (recherche plein
    texte FTS5) puis par force des synapses. « poids » = somme des poids des synapses actives de la note.
    Si aucun mot de la requête ne correspond, renvoie les notes les plus
    reliées (utile pour « que sais-tu du projet A ? »).
    masquer_sensibles=True cache le texte des notes sensibles (utilisé quand
    la réponse part vers une IA en ligne, par exemple Claude via MCP).
    """
    limite = max(1, min(int(limite or 5), 50))
    mots = mots_cles(requete or "")
    notes = projets.lister_notes(projet, racine)
    # Recherche plein texte FTS5 (titres et contenus, sans accents), si disponible.
    fts = projets.rechercher(projet, requete, 50, racine) if mots else []
    scores_fts = {r["id"]: r["score"] for r in fts} if fts is not None else None
    forces = {}
    for s in synapses.lister_synapses(projet, racine, avec_archivees=False):
        for nid in (s["note_source"], s["note_cible"]):
            forces[nid] = forces.get(nid, 0.0) + s["poids"]

    resultats = []
    for n in notes:
        texte = projets.lire_note(projet, n["id"], racine)
        if scores_fts is not None:
            score = scores_fts.get(n["id"], 0.0)
        else:  # repli sans FTS5 : on compte les mots
            titre_norm, texte_norm = normaliser(n["titre"]), normaliser(texte)
            score = sum(3 * titre_norm.count(m) + texte_norm.count(m) for m in mots)
        resultats.append({
            "id": n["id"],
            "titre": n["titre"],
            "extrait": _extrait(texte, mots),
            "poids": round(forces.get(n["id"], 0.0), 3),
            "pertinence": round(score, 4),
            "sensible": bool(n["sensible"]),
            "validee": bool(n.get("validee", 0)),
            "modifiee_le": n["modifiee_le"],
        })

    trouves = [r for r in resultats if r["pertinence"] > 0]
    if mots and trouves:
        resultats = trouves
    resultats.sort(key=lambda r: (r["pertinence"] + r["poids"], r["poids"], r["modifiee_le"]),
                   reverse=True)
    resultats = resultats[:limite]
    for r in resultats:
        r.pop("modifiee_le")
        if masquer_sensibles and r["sensible"]:
            r["extrait"] = MASQUE_SENSIBLE
    return resultats


# ==================================================================
# 2. proposer : créer une proposition en attente, sur copie
# ==================================================================

def proposer(projet, type, contenu, liens=None, titre=None, date=None, racine=None,
             acteur="agent", raison=None, note_cible=None):
    """
    Crée une proposition « en attente ». Rien n'est écrit dans les notes :
    le contenu est rangé dans la table propositions ET dans une copie
    <projet>/propositions/<id>.md. Seul Kayd peut la valider.
    Renvoie l'identifiant de la proposition.
    """
    if type not in TYPES_PROPOSITION:
        raise ValueError(f"Type de proposition refusé : {type!r}. "
                         f"Types permis : {', '.join(TYPES_PROPOSITION)}.")
    contenu = (contenu or "").strip()
    if not contenu:
        raise ValueError("Une proposition doit avoir un contenu.")
    if not titre:
        premiere = contenu.splitlines()[0].lstrip("# ").strip()
        titre = premiere[:80] or "Sans titre"
    liens = [l.strip() for l in (liens or []) if l and l.strip()]
    if type == "modification":
        # Une modification remplace le texte d'une note existante : nouveau texte complet.
        cible = next((n for n in projets.lister_notes(projet, racine)
                      if n["id"] == note_cible), None) if note_cible is not None else None
        if cible is None:
            raise ValueError("Une modification doit viser une note existante (note_cible).")
        titre = titre or f"Modifier « {cible['titre']} »"
    else:
        note_cible = None

    conn = projets._connexion(projet, racine)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO propositions (type, titre, contenu, liens, statut, creee_le, "
                "acteur, raison, note_cible) VALUES (?, ?, ?, ?, 'en attente', ?, ?, ?, ?)",
                (type, titre, contenu, json.dumps(liens, ensure_ascii=False),
                 _date_texte(date), acteur, raison, note_cible))
            pid = cur.lastrowid
            _journal_brut(conn, date, acteur, f"proposition {pid} créée ({type}) : {titre}",
                          raison)
    finally:
        conn.close()

    copie = projets.dossier_projet(projet, racine) / "propositions"
    copie.mkdir(exist_ok=True)
    (copie / f"{pid}.md").write_text(contenu, encoding="utf-8")
    return pid


# ==================================================================
# 3. activer : renforcer les synapses entre notes utilisées ensemble
# ==================================================================

def activer(projet, ids_notes, date=None, racine=None, acteur="agent", raison=None):
    """
    Signale que ces notes ont servi ensemble. Chaque paire de notes
    validées reliée par une synapse compte une activation (gain appliqué
    la nuit suivante). Renvoie {"paires": n, "activees": n, "refusees": n}.
    """
    ids = sorted({int(i) for i in ids_notes})
    bilan = {"paires": 0, "activees": 0, "refusees": 0}
    for a, b in combinations(ids, 2):
        bilan["paires"] += 1
        if not (synapses.note_validee(projet, a, racine)
                and synapses.note_validee(projet, b, racine)):
            bilan["refusees"] += 1
            continue
        if synapses.utiliser_ensemble(projet, a, b, jour(date), racine=racine,
                                      acteur=acteur, raison=raison):
            bilan["activees"] += 1
    return bilan


# ==================================================================
# 4. journal : ajouter une ligne
# ==================================================================

def journal(projet, evenement, raison=None, date=None, racine=None, acteur="agent"):
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            _journal_brut(conn, date, acteur, evenement, raison)
    finally:
        conn.close()


# ==================================================================
# Actions humaines (garde d'écriture)
# ==================================================================

def lire_proposition(projet, pid, racine=None):
    conn = projets._connexion(projet, racine)
    try:
        r = conn.execute("SELECT * FROM propositions WHERE id = ?", (pid,)).fetchone()
    finally:
        conn.close()
    if r is None:
        raise KeyError(f"Aucune proposition {pid} dans le projet {projet!r}.")
    d = dict(r)
    d["liens"] = json.loads(d["liens"] or "[]")
    d["verification"] = json.loads(d["verification"]) if d["verification"] else None
    return d


def lister_propositions(projet, statut=None, racine=None):
    conn = projets._connexion(projet, racine)
    try:
        if statut:
            lignes = conn.execute("SELECT id FROM propositions WHERE statut = ? ORDER BY id",
                                  (statut,)).fetchall()
        else:
            lignes = conn.execute("SELECT id FROM propositions ORDER BY id").fetchall()
    finally:
        conn.close()
    return [lire_proposition(projet, r["id"], racine) for r in lignes]


def _cloturer(projet, pid, statut, resultat_id, date, racine, acteur, raison):
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute(
                "UPDATE propositions SET statut = ?, traitee_le = ?, resultat_id = ? WHERE id = ?",
                (statut, _date_texte(date), resultat_id, pid))
            _journal_brut(conn, date, acteur, f"proposition {pid} {statut}", raison)
    finally:
        conn.close()


def _id_note_par_titre(projet, titre, racine):
    for n in projets.lister_notes(projet, racine):
        if n["titre"] == titre:
            return n["id"]
    return None


def valider_proposition(projet, pid, date=None, racine=None, acteur="kayd", raison=None):
    """
    ACTION HUMAINE. Fait passer une proposition de « en attente » à « écrite » :
    la note (ou la tâche) est alors réellement écrite dans le projet.
    Une note issue d'une proposition validée par Kayd est une note validée.
    Renvoie l'identifiant de la note ou de la tâche créée.
    """
    p = lire_proposition(projet, pid, racine)
    if p["statut"] != "en attente":
        raise ValueError(f"La proposition {pid} est déjà « {p['statut']} ».")
    if p["type"] in ("note", "synthese"):
        contenu = p["contenu"]
        manquants = [l for l in p["liens"] if f"[[{l}]]" not in contenu]
        if manquants:
            contenu += "\n\nLiens : " + " ".join(f"[[{l}]]" for l in manquants) + "\n"
        resultat = projets.creer_note(projet, p["titre"], contenu, type_note=p["type"],
                                      racine=racine, acteur=acteur, validee=True,
                                      raison=f"proposition {pid} validée")
        synapses.relier_note(projet, resultat, jour(date), racine=racine, acteur=acteur)
    elif p["type"] == "modification":
        modifier_note_humaine(projet, p["note_cible"], p["contenu"], date=date, racine=racine,
                              acteur=acteur)
        resultat = p["note_cible"]
    else:  # tache
        note_liee = _id_note_par_titre(projet, p["liens"][0], racine) if p["liens"] else None
        resultat = projets.creer_tache(projet, p["titre"], note_id=note_liee, racine=racine,
                                       acteur=acteur, raison=f"proposition {pid} validée")
    _cloturer(projet, pid, "écrite", resultat, date, racine, acteur, raison)
    return resultat


def refuser_proposition(projet, pid, date=None, racine=None, acteur="kayd", raison=None):
    """ACTION HUMAINE. Refuse une proposition : rien n'est écrit."""
    p = lire_proposition(projet, pid, racine)
    if p["statut"] != "en attente":
        raise ValueError(f"La proposition {pid} est déjà « {p['statut']} ».")
    _cloturer(projet, pid, "refusée", None, date, racine, acteur, raison)


def creer_note_humaine(projet, titre, contenu, sensible=False, date=None, racine=None,
                       acteur="kayd"):
    """ACTION HUMAINE. Kayd écrit lui-même une note : elle est validée d'office."""
    nid = projets.creer_note(projet, titre, contenu, sensible=sensible, racine=racine,
                             acteur=acteur, validee=True)
    synapses.relier_note(projet, nid, jour(date), racine=racine, acteur=acteur)
    return nid


def modifier_note_humaine(projet, note_id, contenu, date=None, racine=None, acteur="kayd"):
    """ACTION HUMAINE. Kayd modifie une note ; les nouveaux [[liens]] créent des synapses."""
    projets.modifier_note(projet, note_id, contenu, racine=racine, acteur=acteur)
    synapses.creer_synapses_de_note(projet, note_id, jour(date), racine=racine, acteur=acteur)


def terminer_tache(projet, tache_id, fait, date=None, racine=None, acteur="kayd"):
    """ACTION HUMAINE. Bouton Fait / Pas fait du contrat d'action."""
    statut = "fait" if fait else "pas fait"
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            cur = conn.execute("UPDATE taches SET statut = ? WHERE id = ?", (statut, tache_id))
            if cur.rowcount == 0:
                raise KeyError(f"Aucune tâche {tache_id} dans le projet {projet!r}.")
            _journal_brut(conn, date, acteur, f"tâche {tache_id} : {statut}", None)
    finally:
        conn.close()
    return statut


# ==================================================================
# Lecture de l'état (réservé à l'orchestrateur et au cockpit)
# ==================================================================

def lister_projets(racine=None):
    return projets.lister_projets(racine)


def projet_sensible(projet, racine=None):
    """Un projet est sensible si un fichier SENSIBLE existe dans son dossier."""
    return (projets.dossier_projet(projet, racine) / "SENSIBLE").exists()


def marquer_projet_sensible(projet, racine=None):
    (projets.dossier_projet(projet, racine) / "SENSIBLE").write_text(
        "Les notes de ce projet ne partent jamais vers une IA gratuite ou en ligne.\n",
        encoding="utf-8")


def projet_demo(projet, racine=None):
    """Un projet de démonstration (fausses données) porte un fichier DEMO dans son dossier."""
    return (projets.dossier_projet(projet, racine) / "DEMO").exists()


def marquer_projet_demo(projet, racine=None):
    (projets.dossier_projet(projet, racine) / "DEMO").write_text(
        "Projet de démonstration : données fictives.\n", encoding="utf-8")


def etat_projet(projet, racine=None):
    conn = projets._connexion(projet, racine)
    try:
        taches = [dict(r) for r in conn.execute("SELECT * FROM taches ORDER BY id")]
    finally:
        conn.close()
    for t in taches:
        t["contrat"] = json.loads(t["contrat"]) if t["contrat"] else None
    return {
        "projet": projet,
        "sensible": projet_sensible(projet, racine),
        "taches": taches,
        "propositions_en_attente": lister_propositions(projet, "en attente", racine),
    }


def lire_journal(projet, limite=50, racine=None):
    lignes = projets.lire_journal(projet, racine)
    return lignes[-limite:]


def annoter_verification(projet, pid, resultat, date=None, racine=None, acteur="agent"):
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute("UPDATE propositions SET verification = ? WHERE id = ?",
                         (json.dumps(resultat, ensure_ascii=False), pid))
            etat = "OK" if resultat.get("ok") else "problèmes : " + "; ".join(resultat["problemes"])
            _journal_brut(conn, date, acteur, f"proposition {pid} vérifiée : {etat}", None)
    finally:
        conn.close()


def enregistrer_contrat(projet, tache_id, contrat, date=None, racine=None, acteur="agent"):
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute("UPDATE taches SET contrat = ? WHERE id = ?",
                         (json.dumps(contrat, ensure_ascii=False), tache_id))
            _journal_brut(conn, date, acteur, f"contrat d'action prêt pour la tâche {tache_id}",
                          contrat.get("pourquoi"))
    finally:
        conn.close()


def titres_et_liens(projet, racine=None):
    """Pour le cerveau 3D : uniquement titres et liens, jamais le contenu."""
    notes = [{"id": n["id"], "titre": n["titre"], "validee": bool(n.get("validee", 0))}
             for n in projets.lister_notes(projet, racine)]
    liens = [{"source": s["note_source"], "cible": s["note_cible"], "poids": s["poids"]}
             for s in synapses.lister_synapses(projet, racine, avec_archivees=False)]
    return notes, liens


def retroliens(projet, note_id, racine=None):
    """Titres des notes qui pointent vers cette note (liens entrants)."""
    titres = {n["id"]: n["titre"] for n in projets.lister_notes(projet, racine)}
    return sorted({titres[s["note_source"]]
                   for s in synapses.lister_synapses(projet, racine)
                   if s["note_cible"] == note_id and s["note_source"] in titres})


# ==================================================================
# Lancement du serveur MCP : python3 -m noyau.corps_calleux
# ==================================================================

if __name__ == "__main__":
    from noyau import serveur_mcp
    serveur_mcp.servir()
