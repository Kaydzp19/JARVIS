"""
Fausse IA de démonstration pour le sommeil et le rêve (marche 6).

Elle reçoit EXACTEMENT les mêmes demandes (texte JSON) qu'une vraie IA,
et répond dans le même format JSON, avec de simples règles de code.
Gratuite, locale, sans clé : rien ne sort de la machine.
"""

import json
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


TACHES = {"synthetiser": synthetiser, "trier": trier, "resumer": resumer}


def repondre(tache, texte, temperature=None):
    demande = json.loads(texte)
    return json.dumps(TACHES[tache](demande, temperature), ensure_ascii=False)
