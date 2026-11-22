"""
Module « notifications » : le premier module branché sur la prise standard.

Il écoute deux événements du noyau :
- contrat_pret   : une tâche vient d'être planifiée (contrat d'action prêt) ;
- tache_terminee : tu as cliqué Fait ou Pas fait.
Il les annonce dans la CONSOLE (la fenêtre du Terminal), les range dans une boîte
locale (~/.jarvis/modules/notifications/boite.txt) et les note au journal.

Mode DEMO et mode REEL font la même chose pour l'instant : un vrai service
(Telegram ou autre) pourra être branché plus tard ici, sans toucher au noyau.
"""


def _message(evenement, donnees):
    if evenement == "contrat_pret":
        return (f"Nouvelle tâche prête [{donnees['projet']}] : {donnees['quoi']} "
                f"({donnees['duree_totale_min']} min). Réponds Fait / Pas fait.")
    if evenement == "tache_terminee":
        verdict = "FAIT" if donnees["statut"] == "fait" else "PAS FAIT"
        return f"Tâche {donnees['tache_id']} [{donnees['projet']}] : {verdict}."
    return f"{evenement} : {donnees}"


def recevoir(evenement, donnees, contexte):
    texte = _message(evenement, donnees)
    contexte.afficher(f"[JARVIS · notification] {texte}")
    with open(contexte.dossier / "boite.txt", "a", encoding="utf-8") as boite:
        boite.write(f"[{contexte.aujourd_hui()}] {texte}\n")
    if "projet" in donnees:
        contexte.journal(donnees["projet"], f"notification ({contexte.mode})", texte)
    return texte
