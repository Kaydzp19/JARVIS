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
from noyau import corps_calleux, modules, routeur_ia, voies
from noyau.outils import jour

STATUTS_A_FAIRE = ("à faire", "pas fait")


def observer(racine=None):
    return [corps_calleux.etat_projet(p, racine) for p in corps_calleux.lister_projets(racine)]


def decider(etats):
    evenements = []
    for e in etats:
        for p in e["propositions_en_attente"]:
            if p["verification"] is None:
                evenements.append({"type": "verifier", "projet": e["projet"], "proposition": p})
        for t in e["taches"]:
            if t["statut"] in STATUTS_A_FAIRE and not t["contrat"]:
                evenements.append({"type": "planifier", "projet": e["projet"], "tache": t,
                                   "sensible": e["sensible"]})
    return evenements


def tour(date=None, racine=None):
    date = jour(date)
    equipe = agents_mod.charger_tous(racine=racine, date=date)
    appels_avant = routeur_ia.nombre_appels(racine)
    etats = observer(racine)
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
