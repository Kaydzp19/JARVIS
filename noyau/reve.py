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

import random
from itertools import combinations

from noyau import synapses

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


def phase_reve(ctx, rejets=None):
    """
    Remplit ctx.idees avec les idées candidates de la nuit.
    rejets : idées déjà rejetées par Kayd, rappelées pour ne pas les répéter.
    """
    ctx.idees, ctx.combinaisons = [], []
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
