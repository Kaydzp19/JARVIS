"""
Module « notifications » (exemple de module, marche 5B).

Mode DEMO : les messages sont écrits dans une boîte locale
            ~/.jarvis/modules/notifications/boite.txt (rien ne sort de la machine).
Mode REEL : pas encore branché (il faudra un service comme Telegram,
            avec ses réglages dans reglages.local).
"""


def _message(evenement, donnees):
    if evenement == "contrat_pret":
        return (f"Nouvelle tâche prête [{donnees['projet']}] : {donnees['quoi']} "
                f"({donnees['duree_totale_min']} min). Réponds Fait / Pas fait.")
    if evenement == "tache_terminee":
        return f"Tâche {donnees['tache_id']} [{donnees['projet']}] : {donnees['statut']}."
    return f"{evenement} : {donnees}"


def recevoir(evenement, donnees, contexte):
    texte = _message(evenement, donnees)
    if contexte.mode == "REEL":
        raise RuntimeError("Mode RÉEL pas encore branché pour les notifications.")
    with open(contexte.dossier / "boite.txt", "a", encoding="utf-8") as boite:
        boite.write(f"[{contexte.aujourd_hui()}] {texte}\n")
    if "projet" in donnees:
        contexte.journal(donnees["projet"], "notification envoyée (DEMO)", texte)
    return texte
