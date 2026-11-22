"""
Routeur IA de JARVIS : la porte unique vers l'intelligence artificielle.

    from noyau import routeur
    routeur.demander_ia("resumer", "courante", sensible=False, texte="…")

Ce fichier est l'entrée courte ; le détail est dans noyau/routeur_ia.py :
- mode SIMULÉ par défaut (réponse factice, sans réseau, sans clé) ;
- table budget_ia (dans ~/.jarvis/systeme.db), plafond 5 €/mois qui BLOQUE l'appel ;
- ordre de préférence : local (Ollama) > Gemini gratuit (non sensible seulement)
  > API payante (plafonnée) ;
- une note sensible ne va JAMAIS vers une offre gratuite (ni payante) : local seulement.
"""

from noyau import reglages, routeur_ia
from noyau.routeur_ia import (AucuneIADisponible, BudgetDepasse, ClaudeAPI,  # noqa: F401
                              GeminiGratuit, IADemo, ModeleLocal, choisir, depense_du_mois,
                              fournisseurs_par_defaut, mode_ia, plafond_mensuel)


def demander_ia(tache, difficulte="courante", sensible=False, texte="", **options):
    """
    tache      : ce qu'on demande (ex. « resumer », « planifier ») ;
    difficulte : courante, difficile ou critique ;
    sensible   : True si la demande contient une note sensible ;
    texte      : le contenu envoyé à l'IA.
    Renvoie {"reponse", "fournisseur", "cout_estime"}.
    """
    return routeur_ia.demander_ia(tache, texte, difficulte, sensible, **options)


def detecter_ollama():
    """
    Le modèle local est-il prêt ? Seulement une DÉTECTION (on demande la liste des
    modèles à Ollama) : aucune question n'est posée au modèle ici.
    """
    local = ModeleLocal()
    modele = local.modele()
    return {"configure": modele, "adresse": local.adresse(),
            "pret": bool(modele) and local.disponible()}


def etat(racine=None):
    """Résumé lisible pour le cockpit et la commande « jarvis ia »."""
    depense = depense_du_mois(racine=racine)
    plafond = plafond_mensuel()
    reel = mode_ia() == "reel"
    return {
        "mode": mode_ia(),
        "budget": {"depense": round(depense, 4), "plafond": plafond,
                   "reste": round(max(0.0, plafond - depense), 4)},
        "ordre": ["local", "gemini (non sensible)", "claude (payant, plafonné)"] if reel
                 else ["simulé"],
        "local": detecter_ollama() if reel else {"configure": None, "pret": False},
        "gemini": {"cle": bool(reglages.lire("CLE_API_GEMINI"))},
        "claude": {"cle": bool(reglages.lire("CLE_API_ANTHROPIC")),
                   "modele": reglages.lire("modele_claude")},
    }
