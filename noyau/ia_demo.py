"""
Fausse IA de démonstration pour le sommeil et le rêve (marche 6).

Elle reçoit EXACTEMENT les mêmes demandes (texte JSON) qu'une vraie IA,
et répond dans le même format JSON, avec de simples règles de code.
Gratuite, locale, sans clé : rien ne sort de la machine.
"""

import json
from collections import Counter

from noyau.outils import mots_cles


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


TACHES = {"synthetiser": synthetiser}


def repondre(tache, texte, temperature=None):
    demande = json.loads(texte)
    return json.dumps(TACHES[tache](demande, temperature), ensure_ascii=False)
