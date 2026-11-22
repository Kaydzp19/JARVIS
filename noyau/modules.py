"""
Prises pour modules (marche 5B) : brancher des services sans toucher au noyau.

Un module = un dossier dans modules/ avec :
    module.json   sa carte d'identité :
                    nom, description,
                    lit        ce qu'il lit (ex. ["taches"]),
                    ecrit      ce qu'il écrit (ex. ["journal", "boite"]),
                    demande    les réglages/secrets nécessaires en mode RÉEL,
                    evenements les événements qu'il écoute
                               (ex. "contrat_pret", "tache_terminee")
    module.py     une fonction recevoir(evenement, donnees, contexte)

Modes : DEMO (fausses données, rien ne sort) ou REEL (vrai service).

Règle d'or : le noyau ne dépend d'aucun module. Si un module est retiré
(dossier supprimé) ou plante, le noyau continue normalement.
"""

import importlib.util
import json
import os
from pathlib import Path

from noyau import corps_calleux, reglages, systeme
from noyau.outils import jour

DOSSIER_PAR_DEFAUT = Path(__file__).resolve().parent.parent / "modules"
MODES = ("DEMO", "REEL")


def dossier_modules():
    return Path(os.environ.get("JARVIS_MODULES", DOSSIER_PAR_DEFAUT))


def decouvrir(dossier=None):
    dossier = Path(dossier or dossier_modules())
    trouves = []
    if not dossier.is_dir():
        return trouves
    for d in sorted(dossier.iterdir()):
        carte = d / "module.json"
        if d.is_dir() and carte.is_file() and (d / "module.py").is_file():
            conf = json.loads(carte.read_text(encoding="utf-8"))
            conf["chemin"] = str(d)
            trouves.append(conf)
    return trouves


def _trouver(nom, dossier=None):
    for m in decouvrir(dossier):
        if m["nom"] == nom:
            return m
    return None


def etat(nom, racine=None):
    conn = systeme.connexion(racine)
    try:
        r = conn.execute("SELECT actif, mode FROM modules WHERE nom = ?", (nom,)).fetchone()
        return {"actif": bool(r["actif"]), "mode": r["mode"]} if r else {"actif": False, "mode": "DEMO"}
    finally:
        conn.close()


def activer(nom, mode="DEMO", racine=None, dossier=None):
    if mode not in MODES:
        raise ValueError(f"Mode inconnu : {mode!r}")
    m = _trouver(nom, dossier)
    if m is None:
        raise KeyError(f"Module introuvable : {nom!r}")
    if mode == "REEL":
        manquants = [c for c in m.get("demande", []) if not reglages.lire(c)]
        if manquants:
            raise ValueError("Mode RÉEL impossible, réglages manquants dans reglages.local : "
                             + ", ".join(manquants))
    conn = systeme.connexion(racine)
    try:
        with conn:
            conn.execute("INSERT INTO modules (nom, actif, mode) VALUES (?, 1, ?) "
                         "ON CONFLICT(nom) DO UPDATE SET actif = 1, mode = excluded.mode",
                         (nom, mode))
    finally:
        conn.close()


def desactiver(nom, racine=None):
    conn = systeme.connexion(racine)
    try:
        with conn:
            conn.execute("UPDATE modules SET actif = 0 WHERE nom = ?", (nom,))
    finally:
        conn.close()


class Contexte:
    """Ce qu'un module a le droit de faire, selon sa carte d'identité."""

    def __init__(self, conf, mode, racine):
        self.nom, self.mode = conf["nom"], mode
        self._ecrit = set(conf.get("ecrit", []))
        base = Path(racine) if racine is not None else reglages.dossier_donnees()
        self.dossier = base / "modules" / conf["nom"]  # ses propres données
        self.dossier.mkdir(parents=True, exist_ok=True)
        self._racine = racine

    def journal(self, projet, evenement, raison=None):
        if "journal" not in self._ecrit:
            raise PermissionError(f"Le module {self.nom} n'a pas déclaré écrire le journal.")
        corps_calleux.journal(projet, evenement, raison, racine=self._racine,
                              acteur=f"module:{self.nom}")

    def afficher(self, texte):
        """Écrire dans la console (le Terminal), si la fiche du module le déclare."""
        if "console" not in self._ecrit:
            raise PermissionError(f"Le module {self.nom} n'a pas déclaré écrire dans la console.")
        print(texte, flush=True)

    def aujourd_hui(self):
        return jour().isoformat()


def _charger_code(conf):
    spec = importlib.util.spec_from_file_location(f"jarvis_module_{conf['nom']}",
                                                  Path(conf["chemin"]) / "module.py")
    code = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(code)
    return code


def emettre(evenement, donnees, racine=None, dossier=None):
    """
    Prévient les modules actifs qui écoutent cet événement.
    Renvoie [{"module", "ok", "resultat" ou "erreur"}]. Ne lève jamais d'erreur :
    un module en panne ne doit pas bloquer le noyau.
    """
    resultats = []
    for conf in decouvrir(dossier):
        if evenement not in conf.get("evenements", []):
            continue
        e = etat(conf["nom"], racine)
        if not e["actif"]:
            continue
        try:
            code = _charger_code(conf)
            r = code.recevoir(evenement, donnees, Contexte(conf, e["mode"], racine))
            resultats.append({"module": conf["nom"], "ok": True, "resultat": r})
        except Exception as ex:
            resultats.append({"module": conf["nom"], "ok": False,
                              "erreur": f"{type(ex).__name__} : {ex}"})
    return resultats
