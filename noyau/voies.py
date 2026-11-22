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


# ==================================================================
# Chaque voie sait aussi PROPOSER (jamais écrire) : la garde d'écriture
# attend la validation de Kayd (python3 -m noyau.valider).
# ==================================================================

def proposer_tache(agent, projet, note, marque):
    """Voie planifier : un projet sans tâche reçoit une proposition de tâche."""
    titre = f"Faire avancer « {note['titre']} »"
    contenu = (f"{titre} : relire la note, décider de la prochaine étape concrète "
               "et la noter dans le journal.")
    pid = agent.proposer(projet, "tache", contenu, liens=[note["titre"]], titre=titre,
                         raison=f"{marque} · le projet n'a plus de tâche à faire")
    agent.journal(projet, f"tâche proposée (proposition {pid})", "aucune tâche à faire")
    return pid


def signaler_liens_casses(agent, projet, note, date, marque):
    """Voie vérifier : une note qui pointe vers une note inexistante reçoit un avertissement."""
    absents = ", ".join(f"« {t} »" for t in note["absents"])
    contenu = (note["contenu"].rstrip() + f"\n\n> ⚠ Lien cassé ({date}) : {absents} ne correspond "
               "à aucune note du projet. Crée la note ou corrige le lien.\n")
    pid = agent.proposer(projet, "modification", contenu, titre=f"Vérifier « {note['titre']} »",
                         raison=f"{marque} · lien vers une note inexistante : {absents}",
                         note_cible=note["id"])
    agent.journal(projet, f"lien cassé signalé (proposition {pid})", absents)
    return pid


def comparer_et_proposer(agent, projet, titre_a, titre_b, marque, sensible_projet=False):
    """Voie comparer : deux notes très proches donnent une note de comparaison proposée."""
    r = comparer(agent, projet, titre_a, titre_b, sensible_projet)
    contenu = (f"# Comparaison : {titre_a} / {titre_b}\n\n{r['resultat']}\n\n"
               f"Voir [[{titre_a}]] et [[{titre_b}]] : faut-il les fusionner ou les distinguer ?\n")
    pid = agent.proposer(projet, "note", contenu, liens=[titre_a, titre_b],
                         titre=f"Comparaison : {titre_a} / {titre_b}"[:80],
                         raison=f"{marque} · deux notes très proches")
    return pid


def proposer_depuis_reve(agent, projet, reve, marque):
    """Voie proposer : une idée rêvée que Kayd a gardée devient une note proposée."""
    titre = ("Idée : " + reve["idee"])[:80]
    liens = " ".join(f"[[{t}]]" for t in reve["sources_titres"])
    contenu = (f"# {titre}\n\n{reve['idee']}\n\nNée du rêve du {reve['date']} "
               f"(score {reve['score']}/10). Notes sources : {liens}\n")
    pid = agent.proposer(projet, "note", contenu, liens=reve["sources_titres"], titre=titre,
                         raison=f"{marque} · idée rêvée gardée par Kayd")
    agent.journal(projet, f"note proposée depuis le rêve n°{reve['id']} (proposition {pid})")
    return pid
