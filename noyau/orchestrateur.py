"""
Orchestrateur de JARVIS (marche 5) : le chef d'équipe.

Un « tour » suit 4 temps, en code simple :
    observer  lire l'état de tous les projets (le seul à voir toutes les tâches)
    décider   repérer les événements : tâche sans plan, proposition non vérifiée
    agir      confier chaque événement à l'agent de la bonne voie
    mesurer   noter le bilan dans le journal (et le renvoyer)

L'IA n'est appelée QUE quand un événement le demande (une tâche à planifier).
Un tour sans événement ne coûte rien.

Garde d'écriture : les agents ne font que proposer ; rien n'est écrit dans
les notes avant la validation de Kayd (corps_calleux.valider_proposition).
"""

from noyau import agent as agents_mod
import re

from noyau import corps_calleux, modules, routeur_ia, voies
from noyau.outils import jour, similarite

STATUTS_A_FAIRE = ("à faire", "pas fait")


SEUIL_PROCHES = 0.5  # deux notes plus semblables que ça méritent une comparaison


def _sans_liens(texte):
    return re.sub(r"\[\[[^\]]*\]\]", " ", texte)


def observer(racine=None, complet=False):
    """
    Lire l'état de tous les projets (le seul à voir toutes les tâches).
    complet=True ajoute ce qu'il faut pour les nouvelles décisions : liens cassés,
    notes très proches, idées rêvées gardées, raisons des propositions déjà faites.
    """
    etats = [corps_calleux.etat_projet(p, racine) for p in corps_calleux.lister_projets(racine)]
    if not complet:
        return etats
    from noyau import reve
    for e in etats:
        p = e["projet"]
        e["raisons"] = [x["raison"] or "" for x in corps_calleux.lister_propositions(p, racine=racine)]
        e["liens_casses"] = corps_calleux.liens_casses(p, racine)
        notes = corps_calleux.se_souvenir(p, "", 50, racine=racine)
        e["notes"] = notes
        valides = [n for n in notes if n["validee"] and not n["sensible"] and not e["sensible"]]
        paires = []
        for i, a in enumerate(valides):
            for b in valides[i + 1:]:
                s = similarite(a["titre"] + " " + _sans_liens(a["extrait"]),
                               b["titre"] + " " + _sans_liens(b["extrait"]))
                if s >= SEUIL_PROCHES:
                    paires.append((s, a, b))
        e["paires_proches"] = sorted(paires, key=lambda x: -x[0])
        e["reves_gardes"] = reve.lister(p, "gardée", racine)
    return etats


def _deja(e, marque):
    return any(r == marque or r.startswith(marque + " ") for r in e.get("raisons", []))


def decider(etats):
    """Décider, en code simple : chaque événement est confié à la voie qui convient."""
    evenements = []
    for e in etats:
        for p in e["propositions_en_attente"]:
            if p["verification"] is None:
                evenements.append({"type": "verifier", "projet": e["projet"], "proposition": p})
        for t in e["taches"]:
            if t["statut"] in STATUTS_A_FAIRE and not t["contrat"]:
                evenements.append({"type": "planifier", "projet": e["projet"], "tache": t,
                                   "sensible": e["sensible"]})
        if "raisons" not in e:
            continue  # observation simple : pas de nouvelles décisions
        p = e["projet"]
        # Voie planifier : plus aucune tâche à faire -> proposer une tâche (une fois par note).
        if not any(t["statut"] in STATUTS_A_FAIRE for t in e["taches"]):
            for n in e["notes"]:
                marque = f"voie:planifier:note:{n['id']}"
                if n["validee"] and not _deja(e, marque):
                    evenements.append({"type": "proposer_tache", "projet": p, "note": n,
                                       "marque": marque})
                    break
        # Voie vérifier : liens [[...]] cassés -> proposition de modification.
        for n in e["liens_casses"]:
            marque = f"voie:verifier:lien:{n['id']}:{','.join(n['absents'])}"
            if not _deja(e, marque):
                evenements.append({"type": "lien_casse", "projet": p, "note": n, "marque": marque})
        # Voie comparer : deux notes très proches -> note de comparaison (une par tour).
        for _, a, b in e["paires_proches"]:
            marque = f"voie:comparer:{min(a['id'], b['id'])},{max(a['id'], b['id'])}"
            if not _deja(e, marque):
                evenements.append({"type": "comparer", "projet": p, "a": a["titre"],
                                   "b": b["titre"], "marque": marque})
                break
        # Voie proposer : une idée rêvée gardée -> note proposée.
        for r in e["reves_gardes"]:
            marque = f"voie:proposer:reve:{r['id']}"
            if not _deja(e, marque):
                evenements.append({"type": "proposer_reve", "projet": p, "reve": r,
                                   "marque": marque})
    return evenements


def tour(date=None, racine=None):
    date = jour(date)
    equipe = agents_mod.charger_tous(racine=racine, date=date)
    appels_avant = routeur_ia.nombre_appels(racine)
    etats = observer(racine, complet=True)
    evenements = decider(etats)
    faits, erreurs = [], []
    for ev in evenements:
        projet = ev["projet"]
        try:
            if ev["type"] == "verifier":
                resultat = voies.verifier(equipe["verificateur"], projet, ev["proposition"])
                corps_calleux.annoter_verification(projet, ev["proposition"]["id"], resultat,
                                                   date=date, racine=racine,
                                                   acteur="agent:verificateur")
                faits.append(f"{projet} : proposition {ev['proposition']['id']} vérifiée")
            elif ev["type"] == "planifier":
                contrat = voies.planifier(equipe["planificateur"], projet, ev["tache"],
                                          ev["sensible"])
                corps_calleux.enregistrer_contrat(projet, ev["tache"]["id"], contrat, date=date,
                                                  racine=racine, acteur="agent:planificateur")
                modules.emettre("contrat_pret", contrat, racine=racine)
                faits.append(f"{projet} : tâche {ev['tache']['id']} planifiée")
            elif ev["type"] == "proposer_tache":
                pid = voies.proposer_tache(equipe["planificateur"], projet, ev["note"], ev["marque"])
                faits.append(f"{projet} : tâche proposée ({pid})")
            elif ev["type"] == "lien_casse":
                pid = voies.signaler_liens_casses(equipe["verificateur"], projet, ev["note"],
                                                  date.isoformat(), ev["marque"])
                faits.append(f"{projet} : lien cassé signalé ({pid})")
            elif ev["type"] == "comparer":
                pid = voies.comparer_et_proposer(equipe["comparateur"], projet, ev["a"], ev["b"],
                                                 ev["marque"])
                faits.append(f"{projet} : comparaison proposée ({pid})")
            elif ev["type"] == "proposer_reve":
                pid = voies.proposer_depuis_reve(equipe["redacteur"], projet, ev["reve"],
                                                 ev["marque"])
                faits.append(f"{projet} : idée rêvée proposée ({pid})")
        except routeur_ia.BudgetDepasse as e:
            erreurs.append(f"{projet} : {e}")
            break  # inutile d'insister ce mois-ci
        except Exception as e:  # un agent qui échoue ne bloque pas les autres
            erreurs.append(f"{projet} : {type(e).__name__} : {e}")

    par_projet = {}
    for f in faits:
        par_projet.setdefault(f.split(" : ")[0], []).append(f)
    for projet, lignes in par_projet.items():
        corps_calleux.journal(projet, f"tour de l'orchestrateur : {len(lignes)} action(s)",
                              "; ".join(l.split(" : ", 1)[1] for l in lignes),
                              date=date, racine=racine, acteur="orchestrateur")
    return {
        "date": date.isoformat(),
        "projets_observes": len(etats),
        "evenements": len(evenements),
        "actions": faits,
        "erreurs": erreurs,
        "appels_ia": routeur_ia.nombre_appels(racine) - appels_avant,
    }


def taches_a_faire(racine=None):
    """Toutes les tâches à faire, tous projets confondus (vue de l'orchestrateur)."""
    liste = []
    for e in observer(racine):
        for t in e["taches"]:
            if t["statut"] in STATUTS_A_FAIRE:
                liste.append(dict(t, projet=e["projet"]))
    liste.sort(key=lambda t: (t["statut"] != "à faire", t["echeance"] or "9999-99-99",
                              t["projet"], t["id"]))
    return liste


def prochaine_action(racine=None):
    """Le contrat d'action de la tâche à faire maintenant (ou None)."""
    for t in taches_a_faire(racine):
        if t["contrat"]:
            return t["contrat"]
    return None


def terminer(projet, tache_id, fait, date=None, racine=None):
    """Bouton Fait / Pas fait."""
    statut = corps_calleux.terminer_tache(projet, tache_id, fait, date=date, racine=racine)
    modules.emettre("tache_terminee", {"projet": projet, "tache_id": tache_id, "statut": statut},
                    racine=racine)
    return statut


def contrat_en_texte(c):
    lignes = [f"QUOI      {c['quoi']}  [{c['projet']}]",
              f"POURQUOI  {c['pourquoi']}"]
    if c.get("ou"):
        lignes.append(f"OÙ        note « {c['ou']['titre']} »")
    lignes.append(f"COMMENT   ({c['duree_totale_min']} min au total)")
    for i, e in enumerate(c["comment"], 1):
        lignes.append(f"   {i}. {e['etape']} ({e['duree_min']} min)")
    lignes.append("FIN       Fait / Pas fait")
    lignes.append(f"APRÈS     {c['apres']}")
    return "\n".join(lignes)
