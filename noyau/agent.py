"""
Agents configurables (marche 5).

Un agent = un petit fichier JSON dans noyau/agents/ :
    nom       son nom
    voie      planifier, proposer, comparer ou verifier
    consigne  ce qu'il doit faire, en une phrase
    outils    la liste des SEULS outils qu'il a le droit d'utiliser,
              parmi : se_souvenir, proposer, activer, journal, ia

Un agent n'a aucun moyen d'écrire directement dans les notes : ses seuls
outils d'écriture sont « proposer » (en attente de Kayd), « activer » et
« journal ». Il n'existe aucun outil pour publier, payer ou supprimer.
"""

import json
from pathlib import Path

from noyau import corps_calleux, routeur_ia

DOSSIER_AGENTS = Path(__file__).resolve().parent / "agents"
OUTILS_PERMIS = ("se_souvenir", "proposer", "activer", "journal", "ia")
VOIES = ("planifier", "proposer", "comparer", "verifier")


class OutilInterdit(PermissionError):
    pass


class Agent:

    def __init__(self, nom, voie, consigne, outils, racine=None, date=None):
        if voie not in VOIES:
            raise ValueError(f"Voie inconnue : {voie!r}")
        inconnus = set(outils) - set(OUTILS_PERMIS)
        if inconnus:
            raise ValueError(f"Outils inconnus pour l'agent {nom} : {sorted(inconnus)}")
        self.nom, self.voie, self.consigne = nom, voie, consigne
        self.outils = list(outils)
        self.racine, self.date = racine, date

    @property
    def acteur(self):
        return f"agent:{self.nom}"

    def _verifier(self, outil):
        if outil not in self.outils:
            raise OutilInterdit(f"L'agent {self.nom} n'a pas le droit d'utiliser « {outil} ».")

    # --- Les outils, tous via le corps calleux ---

    def se_souvenir(self, projet, requete="", limite=5):
        self._verifier("se_souvenir")
        return corps_calleux.se_souvenir(projet, requete, limite, racine=self.racine)

    def proposer(self, projet, type, contenu, liens=None, titre=None, raison=None,
                 note_cible=None):
        self._verifier("proposer")
        return corps_calleux.proposer(projet, type, contenu, liens, titre=titre, date=self.date,
                                      racine=self.racine, acteur=self.acteur, raison=raison,
                                      note_cible=note_cible)

    def activer(self, projet, ids_notes):
        self._verifier("activer")
        return corps_calleux.activer(projet, ids_notes, date=self.date, racine=self.racine,
                                     acteur=self.acteur)

    def journal(self, projet, evenement, raison=None):
        self._verifier("journal")
        corps_calleux.journal(projet, evenement, raison, date=self.date, racine=self.racine,
                              acteur=self.acteur)

    def ia(self, tache, texte, difficulte="courante", sensible=False):
        self._verifier("ia")
        return routeur_ia.demander_ia(tache, texte, difficulte, sensible, date=self.date,
                                      racine=self.racine)

    def decrire(self):
        return {"nom": self.nom, "voie": self.voie, "consigne": self.consigne,
                "outils": self.outils}


def charger(nom, racine=None, date=None, dossier=None):
    chemin = Path(dossier or DOSSIER_AGENTS) / f"{nom}.json"
    conf = json.loads(chemin.read_text(encoding="utf-8"))
    return Agent(conf["nom"], conf["voie"], conf["consigne"], conf["outils"],
                 racine=racine, date=date)


def charger_tous(racine=None, date=None, dossier=None):
    dossier = Path(dossier or DOSSIER_AGENTS)
    return {p.stem: charger(p.stem, racine, date, dossier) for p in sorted(dossier.glob("*.json"))}
