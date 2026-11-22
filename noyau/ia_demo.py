"""
Fausse IA de démonstration pour le sommeil et le rêve (marche 6).

Elle reçoit EXACTEMENT les mêmes demandes (texte JSON) qu'une vraie IA,
et répond dans le même format JSON, avec de simples règles de code.
Gratuite, locale, sans clé : rien ne sort de la machine.
"""

import hashlib
import json
import random
import re
from collections import Counter

from datetime import date

from noyau.outils import mots_cles, similarite


def _frequents(textes, n=5):
    return [m for m, _ in Counter(m for t in textes for m in mots_cles(t)).most_common(n)]


def synthetiser(demande, temperature):
    notes = demande.get("notes", [])
    mots = _frequents([n.get("titre", "") + " " + n.get("extrait", "") for n in notes])
    titres = ", ".join(n.get("titre", "") for n in notes)
    return {"resume": f"Ces notes ({titres}) tournent autour de : "
                      + (", ".join(mots) or "thèmes variés")
                      + ". Elles servent souvent ensemble : les regrouper aide à retrouver "
                        "l'idée d'ensemble."}


def trier(demande, temperature):
    notes = demande.get("notes", [])
    aujourd_hui = date.fromisoformat(demande["aujourd_hui"])
    limite = int(demande.get("peremption_jours", 90))
    def sans_liens(n):  # les [[liens]] ne disent rien du sujet de la note elle-même
        return n["titre"] + " " + re.sub(r"\[\[[^\]]*\]\]", " ", n["extrait"])

    doublons = []
    for i, a in enumerate(notes):
        for b in notes[i + 1:]:
            s = similarite(sans_liens(a), sans_liens(b))
            if s >= 0.6:
                doublons.append({"notes": sorted([a["id"], b["id"]]),
                                 "raison": f"mots en commun à {int(s * 100)} %"})
    orphelines = [{"note": n["id"], "raison": "aucun lien avec une autre note"}
                  for n in notes if n.get("liens_actifs", 0) == 0]
    perimees = []
    for n in notes:
        age = (aujourd_hui - date.fromisoformat(n["modifiee_le"][:10])).days
        if age > limite:
            perimees.append({"note": n["id"], "raison": f"pas modifiée depuis {age} jours"})
    return {"doublons": doublons, "orphelines": orphelines, "perimees": perimees}


def resumer(demande, temperature):
    s = demande.get("statistiques", {})
    notes = demande.get("notes", [])
    phrases = [f"Le projet compte {s.get('notes', 0)} note(s), dont {s.get('notes_validees', 0)} "
               f"validée(s), reliées par {s.get('synapses_actives', 0)} synapse(s) active(s)."]
    if s.get("notes_centrales"):
        phrases.append("Notes centrales : " + ", ".join(s["notes_centrales"]) + ".")
    mots = _frequents([n.get("titre", "") + " " + n.get("extrait", "") for n in notes])
    if mots:
        phrases.append("Thèmes dominants : " + ", ".join(mots) + ".")
    phrases.append(f"{s.get('taches_a_faire', 0)} tâche(s) à faire, "
                   f"{s.get('taches_faites', 0)} faite(s), "
                   f"{s.get('propositions_en_attente', 0)} proposition(s) en attente de validation.")
    if s.get("propositions_en_attente"):
        phrases.append("Prochaine étape utile : trier les propositions en attente.")
    elif s.get("taches_a_faire"):
        phrases.append("Prochaine étape utile : avancer la tâche la plus urgente.")
    return {"resume": " ".join(phrases)}


# Modèles d'idées, génériques (aucun domaine précis) : {a}, {b}, {c} = titres des notes.
IDEES_PAIRES = [
    ("Appliquer la logique de « {a} » à « {b} » : écrire une note qui transpose l'une dans "
     "l'autre.", "faible", 0),
    ("Tester pendant une semaine « {a} » au service de « {b} », puis noter ce qui a marché.",
     "faible", 0),
    ("Créer un mini-guide qui relie « {a} » et « {b} » pour quelqu'un qui découvre le sujet.",
     "moyen", 0),
    ("Construire un petit outil automatique qui fait le lien entre « {a} » et « {b} ».",
     "fort", 30),
    ("Demander l'avis de trois personnes sur le croisement « {a} » × « {b} ».", "faible", 0),
    ("Transformer « {a} » et « {b} » en un format nouveau (fiche, vidéo courte, atelier).",
     "moyen", 20),
]
IDEES_TRIPLETS = [
    ("Écrire une checklist commune à « {a} », « {b} » et « {c} ».", "faible", 0),
    ("Dessiner une carte qui montre comment « {a} », « {b} » et « {c} » se répondent.",
     "faible", 0),
    ("Lancer un petit projet pilote qui réunit « {a} », « {b} » et « {c} ».", "fort", 50),
]


def rever(demande, temperature):
    graine = hashlib.sha256(json.dumps(demande, sort_keys=True).encode()).hexdigest()
    rng = random.Random(graine)
    rejetees = [r.get("idee", "") for r in demande.get("idees_rejetees", [])]
    combos = demande.get("combinaisons", [])
    idees, essais = [], 0
    while combos and len(idees) < demande.get("nombre_idees", 5) and essais < 60:
        essais += 1
        notes = combos[len(idees) % len(combos)]["notes"] if essais < 30 else rng.choice(combos)["notes"]
        modeles = IDEES_TRIPLETS if len(notes) >= 3 else IDEES_PAIRES
        modele, effort, cout = rng.choice(modeles)
        titres = dict(zip("abc", (n["titre"] for n in notes)))
        texte = modele.format(**titres)
        if any(texte == i["idee"] for i in idees):
            continue
        if any(similarite(texte, r) >= 0.6 for r in rejetees):
            continue  # ressemble trop à une idée déjà rejetée
        idees.append({"idee": texte, "sources": [n["id"] for n in notes],
                      "effort": effort, "cout_estime_eur": cout})
    return {"idees": idees}


def evaluer(demande, temperature):
    c = demande.get("contraintes", {})
    objectifs = set(mots_cles(c.get("objectifs", "")))
    budget = float(c.get("budget_eur") or 0)
    debutant = "debut" in (c.get("niveau") or "").lower().replace("é", "e")
    deja = (demande.get("titres_existants", []) + demande.get("idees_deja_vues", []))
    rejetees = [r.get("idee", "") for r in demande.get("idees_rejetees", [])]
    evaluations = []
    for idee in demande.get("idees", []):
        texte = idee["idee"]
        proche = max([similarite(texte, x) for x in deja] or [0.0])
        proche_rejet = max([similarite(texte, x) for x in rejetees] or [0.0])
        nouveaute = 10 * (1 - proche) * (0.3 if proche_rejet >= 0.4 else 1)
        mots = set(mots_cles(texte + " " + " ".join(idee.get("sources_titres", []))))
        utilite = 3 + 7 * len(mots & objectifs) / len(objectifs) if objectifs else 5.0
        faisabilite = {"faible": 9, "moyen": 6, "fort": 3}.get(idee.get("effort"), 5)
        if debutant and idee.get("effort") == "fort":
            faisabilite = 2
        if float(idee.get("cout_estime_eur") or 0) > budget:
            faisabilite = 1
        raisons = []
        raisons.append("très nouvelle" if nouveaute >= 7 else "proche de l'existant")
        raisons.append(f"sert {len(mots & objectifs)} objectif(s)" if objectifs
                       else "objectifs non renseignés")
        raisons.append(f"effort {idee.get('effort')}, coût {idee.get('cout_estime_eur', 0)} € "
                       f"pour un budget de {budget:g} €")
        evaluations.append({"index": idee["index"], "nouveaute": round(nouveaute, 1),
                            "utilite": round(min(10, utilite), 1),
                            "faisabilite": faisabilite, "justification": " ; ".join(raisons)})
    return {"evaluations": evaluations}


TACHES = {"synthetiser": synthetiser, "trier": trier, "resumer": resumer, "rever": rever,
          "evaluer": evaluer}


def repondre(tache, texte, temperature=None):
    demande = json.loads(texte)
    return json.dumps(TACHES[tache](demande, temperature), ensure_ascii=False)
