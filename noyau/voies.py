"""
Les quatre voies de travail des agents (marche 5) : planifier, proposer,
comparer, vérifier. Chaque voie reçoit un agent et n'utilise que ses outils.
"""

from noyau import routeur_ia
from noyau.outils import normaliser

ETAPES_PAR_DEFAUT = [
    {"etape": "Préparer ce qu'il faut", "duree_min": 10},
    {"etape": "Faire la tâche", "duree_min": 25},
    {"etape": "Vérifier et noter le résultat", "duree_min": 5},
]

# Mots qui signalent une action qu'aucun agent ne doit faire seul.
ACTIONS_SENSIBLES = ("publier", "publication", "payer", "paiement", "virement", "acheter",
                     "supprimer", "suppression", "effacer")


def _notes_du_projet(agent, projet):
    return agent.se_souvenir(projet, "", 50)


# ------------------------------------------------------------------
# planifier : tâche -> contrat d'action
# ------------------------------------------------------------------

def planifier(agent, projet, tache, sensible_projet=False):
    notes = _notes_du_projet(agent, projet)
    note = next((n for n in notes if n["id"] == tache.get("note_id")), None)
    if note is None:
        trouvees = agent.se_souvenir(projet, tache["titre"], 1)
        note = trouvees[0] if trouvees and trouvees[0]["pertinence"] > 0 else None
    sensible = sensible_projet or bool(note and note["sensible"])
    reponse = agent.ia("planifier", tache["titre"], "courante", sensible)
    etapes = routeur_ia.etapes_depuis_texte(reponse["reponse"])[:3]
    if len(etapes) < 3:
        etapes = ETAPES_PAR_DEFAUT

    pourquoi = (f"Elle fait avancer « {note['titre']} »." if note
                else f"C'est la prochaine tâche du projet {projet}.")
    if tache.get("echeance"):
        pourquoi += f" Échéance : {tache['echeance']}."
    contrat = {
        "projet": projet,
        "tache_id": tache["id"],
        "quoi": tache["titre"],
        "pourquoi": pourquoi,
        "ou": {"note_id": note["id"], "titre": note["titre"]} if note else None,
        "comment": etapes,
        "duree_totale_min": sum(e["duree_min"] for e in etapes),
        "fin": ["Fait", "Pas fait"],
        "apres": "Pause de 5 minutes, puis tâche suivante.",
        "ia": reponse["fournisseur"],
    }
    agent.journal(projet, f"tâche {tache['id']} planifiée", f"IA utilisée : {reponse['fournisseur']}")
    return contrat


# ------------------------------------------------------------------
# proposer : nouvelle note / tâche, en attente de Kayd
# ------------------------------------------------------------------

def proposer(agent, projet, type, contenu, liens=None, titre=None, raison=None):
    return agent.proposer(projet, type, contenu, liens, titre=titre, raison=raison)


# ------------------------------------------------------------------
# comparer : ce que deux notes ont en commun
# ------------------------------------------------------------------

def comparer(agent, projet, titre_a, titre_b, sensible_projet=False):
    a = agent.se_souvenir(projet, titre_a, 1)
    b = agent.se_souvenir(projet, titre_b, 1)
    if not a or not b:
        raise KeyError("Note introuvable pour la comparaison.")
    a, b = a[0], b[0]
    sensible = sensible_projet or a["sensible"] or b["sensible"]
    reponse = agent.ia("comparer", a["extrait"] + "\n" + b["extrait"], "courante", sensible)
    agent.journal(projet, f"comparaison : {a['titre']} / {b['titre']}", None)
    return {"a": a["titre"], "b": b["titre"], "resultat": reponse["reponse"]}


# ------------------------------------------------------------------
# verifier : contrôle d'une proposition avant que Kayd la voie
# ------------------------------------------------------------------

def verifier(agent, projet, proposition):
    problemes = []
    if not proposition["titre"].strip():
        problemes.append("titre vide")
    if len(proposition["contenu"].strip()) < 10:
        problemes.append("contenu trop court")
    titres = {n["titre"] for n in _notes_du_projet(agent, projet)}
    absents = [l for l in proposition["liens"] if l not in titres]
    if absents:
        problemes.append("liens vers des notes inexistantes : " + ", ".join(absents))
    texte = normaliser(proposition["titre"] + " " + proposition["contenu"])
    sensibles = [m for m in ACTIONS_SENSIBLES if m in texte]
    if sensibles:
        problemes.append("action sensible (" + ", ".join(sensibles) +
                         ") : à faire uniquement par Kayd, jamais par un agent")
    return {"ok": not problemes, "problemes": problemes, "verifie_par": agent.nom}
