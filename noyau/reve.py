"""
Le rêve de JARVIS (marche 6, phases 3 et 4 du sommeil).

Phase rêve   : on tire au hasard des paires ou triplets de notes ÉLOIGNÉES
               (peu ou pas de synapse entre elles) ; une IA créative
               (température haute) imagine environ 5 idées en les croisant.
Phase réveil : une 2e IA, rigoureuse (température basse), note chaque idée
               (nouveauté, utilité, faisabilité selon tes contraintes) et ne
               garde que la meilleure : une seule idée par projet et par nuit.

Le rêve ne fait que PROPOSER : il n'écrit jamais dans les notes.
Les notes sensibles n'y participent jamais.
"""

import json
import random
from itertools import combinations

from noyau import corps_calleux, projets, reglages, synapses
from noyau.outils import jour

REGLAGES_REVE = {
    "combinaisons": 6,          # nombre de paires/triplets tirés au hasard
    "poids_max": 0.08,          # au-dessus, deux notes sont trop proches pour rêver
                                # (un lien neuf pèse 0,10 : il faut une dizaine de nuits sans usage)
    "nb_idees": 5,              # nombre d'idées demandées à l'IA créative
    "temperature_reve": 1.0,    # IA créative
    "temperature_reveil": 0.2,  # IA rigoureuse
    "score_min": 4.0,           # sous ce score (sur 10), aucune idée n'est gardée
}
EFFORTS = ("faible", "moyen", "fort")


def _reglage(ctx, cle):
    return ctx.r.get(cle, REGLAGES_REVE[cle])


def poids_entre(projet, racine=None):
    """{frozenset({a, b}): poids le plus fort entre a et b} pour les synapses actives."""
    poids = {}
    for s in synapses.lister_synapses(projet, racine, avec_archivees=False):
        cle = frozenset((s["note_source"], s["note_cible"]))
        poids[cle] = max(poids.get(cle, 0.0), s["poids"])
    return poids


def tirer_combinaisons(notes, poids, nombre, poids_max, graine):
    """Paires ou triplets de notes dont TOUTES les paires sont éloignées (poids < poids_max)."""
    rng = random.Random(graine)
    ids = sorted(n["id"] for n in notes)
    vues, choisies = set(), []
    if len(ids) < 2:
        return choisies
    for _ in range(300):
        if len(choisies) >= nombre:
            break
        taille = 3 if len(ids) >= 3 and rng.random() < 0.35 else 2
        combo = tuple(sorted(rng.sample(ids, taille)))
        if combo in vues:
            continue
        vues.add(combo)
        if all(poids.get(frozenset(p), 0.0) < poids_max for p in combinations(combo, 2)):
            choisies.append(combo)
    return choisies


# ------------------------------------------------------------------
# Table « reves » (dans projet.db)
# ------------------------------------------------------------------

def _ligne(r):
    d = dict(r)
    for cle in ("sources", "sources_titres", "details"):
        d[cle] = json.loads(d[cle])
    return d


def lister(projet, statut=None, racine=None):
    conn = projets._connexion(projet, racine)
    try:
        if statut:
            lignes = conn.execute("SELECT * FROM reves WHERE statut = ? ORDER BY id",
                                  (statut,)).fetchall()
        else:
            lignes = conn.execute("SELECT * FROM reves ORDER BY id").fetchall()
    finally:
        conn.close()
    return [_ligne(r) for r in lignes]


def lister_tous(statut=None, racine=None):
    """Les rêves de tous les projets (vue de Kayd), chacun avec son projet."""
    return [dict(r, projet=p) for p in corps_calleux.lister_projets(racine)
            for r in lister(p, statut, racine)]


def trouver(identifiant, racine=None):
    """
    « Demo-A:3 » ou « 3 ». Renvoie (projet, id). Un simple numéro doit être
    sans ambiguïté (un seul projet a un rêve avec ce numéro).
    """
    texte = str(identifiant)
    if ":" in texte:
        projet, num = texte.rsplit(":", 1)
        rid = int(num)
        if not any(r["id"] == rid for r in lister(projet, racine=racine)):
            raise KeyError(f"Aucun rêve {texte}.")
        return projet, rid
    rid = int(texte)
    trouves = [r["projet"] for r in lister_tous(racine=racine) if r["id"] == rid]
    if not trouves:
        raise KeyError(f"Aucun rêve n°{rid}.")
    if len(trouves) > 1:
        raise KeyError(f"Le rêve n°{rid} existe dans plusieurs projets ({', '.join(trouves)}) : "
                       f"précise, par exemple « {trouves[0]}:{rid} ».")
    return trouves[0], rid


def lire(projet, rid, racine=None):
    for r in lister(projet, racine=racine):
        if r["id"] == rid:
            return r
    raise KeyError(f"Aucun rêve n°{rid} dans le projet {projet!r}.")


def changer_statut(projet, rid, statut, raison=None, date=None, racine=None, acteur="kayd"):
    """ACTION HUMAINE : décider du sort d'une idée rêvée."""
    if statut not in ("gardée", "rejetée", "creusée"):
        raise ValueError(f"Statut impossible : {statut!r}")
    r = lire(projet, rid, racine)
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute("UPDATE reves SET statut = ?, raison = ?, traite_le = ? WHERE id = ?",
                         (statut, raison or r["raison"], jour(date).isoformat(), rid))
    finally:
        conn.close()
    corps_calleux.journal(projet, f"rêve n°{rid} {statut} : {r['idee']}", raison, date=date,
                          racine=racine, acteur=acteur)
    return lire(projet, rid, racine)


def garder(projet, rid, raison=None, date=None, racine=None):
    return changer_statut(projet, rid, "gardée", raison, date, racine)


def rejeter(projet, rid, raison=None, date=None, racine=None):
    return changer_statut(projet, rid, "rejetée", raison, date, racine)


def deja_reve(projet, date, racine=None):
    """Une seule idée par projet et par nuit."""
    return any(r["date"] == date.isoformat() for r in lister(projet, racine=racine))


def _enregistrer(ctx, idee, score, details, raison):
    conn = projets._connexion(ctx.projet, ctx.racine)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO reves (date, idee, sources, sources_titres, score, details, "
                "statut, raison) VALUES (?, ?, ?, ?, ?, ?, 'nouvelle', ?)",
                (ctx.date.isoformat(), idee["idee"], json.dumps(idee["sources"]),
                 json.dumps(idee["sources_titres"], ensure_ascii=False), score,
                 json.dumps(details, ensure_ascii=False), raison))
            return cur.lastrowid
    finally:
        conn.close()


def contraintes():
    """Tes contraintes, lues dans reglages.local (budget, niveau, objectifs)."""
    return {"budget_eur": reglages.lire_nombre("CONTRAINTE_BUDGET_EUR", 0.0),
            "niveau": reglages.lire("CONTRAINTE_NIVEAU"),
            "objectifs": reglages.lire("CONTRAINTE_OBJECTIFS")}


# ------------------------------------------------------------------
# Phase rêve
# ------------------------------------------------------------------

def phase_reve(ctx, rejets=None):
    """
    Remplit ctx.idees avec les idées candidates de la nuit.
    rejets : idées déjà rejetées par Kayd, rappelées pour ne pas les répéter.
    """
    ctx.idees, ctx.combinaisons = [], []
    if deja_reve(ctx.projet, ctx.date, ctx.racine):
        ctx.journal("sommeil · rêve", "déjà rêvé cette nuit : une seule idée par nuit")
        return {"idees_revees": 0}
    notes = ctx.notes_partageables()
    if len(notes) < 2:
        ctx.journal("sommeil · rêve", "pas assez de notes partageables pour rêver "
                    "(les notes sensibles sont exclues)")
        return {"idees_revees": 0}
    par_id = {n["id"]: n for n in notes}
    combos = tirer_combinaisons(notes, poids_entre(ctx.projet, ctx.racine),
                                _reglage(ctx, "combinaisons"), _reglage(ctx, "poids_max"),
                                graine=f"{ctx.projet}|{ctx.date.isoformat()}")
    if not combos:
        ctx.journal("sommeil · rêve", "aucune paire de notes éloignées : toutes sont déjà liées")
        return {"idees_revees": 0}
    nb = _reglage(ctx, "nb_idees")
    demande = {
        "consigne": (f"Tu rêves. Croise ces notes qui n'ont presque rien à voir entre elles et "
                     f"imagine environ {nb} idées nouvelles, concrètes et surprenantes. Pour chaque "
                     "idée, donne les identifiants des notes sources, l'effort (faible, moyen ou "
                     "fort) et un coût estimé en euros. Ne reprends aucune idée déjà rejetée. "
                     'Réponds en JSON : {"idees": [{"idee": "...", "sources": [id, id], '
                     '"effort": "faible", "cout_estime_eur": 0}]}'),
        "nombre_idees": nb,
        "combinaisons": [{"notes": [{"id": i, "titre": par_id[i]["titre"],
                                     "extrait": par_id[i]["extrait"][:160]} for i in c]}
                         for c in combos],
        "idees_rejetees": rejets or [],
    }
    reponse = ctx.nuit.ia("rever", demande, "courante", sensible=False,
                          temperature=_reglage(ctx, "temperature_reve"))
    idees = []
    for item in (reponse["donnees"] or {}).get("idees", []):
        texte = str(item.get("idee") or "").strip()
        sources = [i for i in (item.get("sources") or []) if i in par_id]
        if not texte or len(set(sources)) < 2:
            continue  # idée vide ou sans notes sources valables : écartée
        effort = item.get("effort") if item.get("effort") in EFFORTS else "moyen"
        try:
            cout = max(0.0, float(item.get("cout_estime_eur") or 0))
        except (TypeError, ValueError):
            cout = 0.0
        idees.append({"idee": texte, "sources": sorted(set(sources)),
                      "sources_titres": [par_id[i]["titre"] for i in sorted(set(sources))],
                      "effort": effort, "cout_estime_eur": cout})
    ctx.idees, ctx.combinaisons = idees, combos
    ctx.journal("sommeil · rêve",
                f"{len(combos)} combinaison(s) de notes éloignées, {len(idees)} idée(s) imaginée(s) "
                f"par l'IA créative ({reponse['fournisseur']})")
    return {"idees_revees": len(idees)}


# ------------------------------------------------------------------
# Phase réveil
# ------------------------------------------------------------------

def phase_reveil(ctx, rejets=None):
    """Une IA rigoureuse note les idées ; on ne garde que la meilleure (ou aucune)."""
    idees = getattr(ctx, "idees", [])
    if not idees:
        ctx.journal("sommeil · réveil", "aucune idée à évaluer cette nuit")
        return {"reve": None}
    anciens = lister(ctx.projet, racine=ctx.racine)
    demande = {
        "consigne": ("Tu es un évaluateur rigoureux et exigeant. Note chaque idée de 0 à 10 sur : "
                     "nouveauté (différente des notes existantes et des idées déjà vues), utilité "
                     "(sert les objectifs), faisabilité (compatible avec le budget et le niveau). "
                     "Sois sévère et justifie en une phrase. Réponds en JSON : "
                     '{"evaluations": [{"index": 0, "nouveaute": 0, "utilite": 0, '
                     '"faisabilite": 0, "justification": "..."}]}'),
        "contraintes": contraintes(),
        "idees": [dict(idee, index=i) for i, idee in enumerate(idees)],
        "titres_existants": [n["titre"] for n in ctx.notes_partageables()],
        "idees_deja_vues": [a["idee"] for a in anciens],
        "idees_rejetees": rejets or [],
    }
    reponse = ctx.nuit.ia("evaluer", demande, "difficile", sensible=False,
                          temperature=_reglage(ctx, "temperature_reveil"))
    notees = []
    for ev in (reponse["donnees"] or {}).get("evaluations", []):
        try:
            i = int(ev["index"])
            n, u, f = (max(0.0, min(10.0, float(ev[k])))
                       for k in ("nouveaute", "utilite", "faisabilite"))
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= i < len(idees):
            notees.append((round((n + u + f) / 3, 1), i,
                           {"nouveaute": n, "utilite": u, "faisabilite": f},
                           str(ev.get("justification") or "")))
    if not notees:
        ctx.journal("sommeil · réveil", "évaluation illisible : aucune idée gardée")
        return {"reve": None}
    score, i, details, justification = max(notees, key=lambda t: (t[0], -t[1]))
    if score < _reglage(ctx, "score_min"):
        ctx.journal("sommeil · réveil",
                    f"aucune idée assez bonne (meilleur score {score}/10, minimum "
                    f"{_reglage(ctx, 'score_min')})")
        return {"reve": None}
    details = dict(details, effort=idees[i]["effort"], cout_estime_eur=idees[i]["cout_estime_eur"],
                   idees_evaluees=len(notees), ia=reponse["fournisseur"])
    rid = _enregistrer(ctx, idees[i], score, details, justification)
    ctx.journal("sommeil · réveil",
                f"idée n°{rid} gardée sur {len(notees)} (score {score}/10) : {idees[i]['idee']} "
                f"— sources : {', '.join(idees[i]['sources_titres'])} — {justification}")
    return {"reve": rid}
