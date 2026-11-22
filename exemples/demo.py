"""
Démonstration de JARVIS (fausses données, rien de personnel, IA simulée, 0 €).

    python3 exemples/demo.py               crée la démo puis ouvre l'interface
    python3 exemples/demo.py --remplacer   la recrée de zéro

Ce que fait la démo, dans l'ordre :
  1. crée 2 projets fictifs : « Projet A » (normal) et « Projet B » (sensible) ;
  2. écrit et VALIDE des notes, relie certaines par des [[liens]] ;
  3. simule quelques jours d'usage, puis lance une nuit (tri, analyse, rêve, réveil) ;
  4. génère des propositions (slogan, tri, synthèse) qui attendent ta validation ;
  5. ouvre l'interface (cerveau 3D + cockpit) dans ton navigateur.

Les données de démo vont dans ~/.jarvis/demo/ : elles ne se mêlent jamais à tes
vrais projets (~/.jarvis/projets/). Supprimer ce dossier efface la démo.
"""

import shutil
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noyau import agent as agents_mod  # noqa: E402
from noyau import corps_calleux as cc  # noqa: E402
from noyau import orchestrateur, projets, sommeil, synapses, voies  # noqa: E402
from noyau.outils import jour  # noqa: E402

PROJETS_DEMO = ("Projet A", "Projet B")


def creer_demo(racine=None, aujourd_hui=None, remplacer=False, bavard=True):
    aujourd_hui = jour(aujourd_hui)
    debut = aujourd_hui - timedelta(days=5)
    existants = set(projets.lister_projets(racine))
    if existants & set(PROJETS_DEMO):
        if not remplacer:
            if bavard:
                print("La démo existe déjà (on la réutilise). Pour la recréer : --remplacer")
            return False
        for nom in PROJETS_DEMO:
            shutil.rmtree(projets.dossier_projet(nom, racine), ignore_errors=True)

    # ---------------- Projet A : projet ordinaire ----------------
    projets.creer_projet("Projet A", racine=racine, acteur="demo", raison="projet de démonstration")
    cc.marquer_projet_demo("Projet A", racine=racine)
    note = lambda titre, texte, **k: cc.creer_note_humaine("Projet A", titre, texte, date=debut,
                                                            racine=racine, acteur="demo", **k)
    objectif = note("Objectif", "# Objectif\nLancer la première version du site vitrine dans "
                    "un mois.\nPublic visé : voir [[Clients cibles]]. Ce qu'on vend : [[Offre]].")
    clients = note("Clients cibles", "# Clients cibles\nPetites entreprises du quartier qui "
                   "n'ont pas encore de site.\nElles veulent un prix clair : [[Prix]]. "
                   "Ce qu'on leur propose : [[Offre]].")
    offre = note("Offre", "# Offre\nUn site d'une page, livré en une semaine, avec "
                 "formulaire de contact.\nTarif : [[Prix]].")
    prix = note("Prix", "# Prix\n490 € la page, 20 € par mois d'hébergement.\n"
                "À tester auprès des [[Clients cibles]].")
    # Une note écrite « par l'IA » et pas encore validée : elle ne renforce rien.
    brouillon = projets.creer_note("Projet A", "Idées en vrac",
                                   "Pistes à trier. Peut-être lié à [[Objectif]].",
                                   racine=racine, acteur="agent:redacteur")
    synapses.relier_note("Projet A", brouillon, debut, racine=racine, acteur="demo")

    # Pour le tri de nuit : un doublon de « Prix » et une note périmée.
    note("Tarifs", "# Tarifs\nPrix : 490 € la page, 20 € par mois d'hébergement, "
                   "à tester auprès des clients.")
    ancienne = projets.creer_note("Projet A", "Liste de concurrents",
                                  "# Liste de concurrents\nTrois agences repérées l'an dernier. "
                                  "Voir [[Offre]].", racine=racine, acteur="demo", validee=True,
                                  horodatage=(aujourd_hui - timedelta(days=200)).isoformat()
                                  + "T09:00:00")
    synapses.relier_note("Projet A", ancienne, debut, racine=racine, acteur="demo")
    # Pour le rêve : des notes sans rapport entre elles (notes éloignées).
    note("Atelier du samedi", "# Atelier du samedi\nAnimer un atelier gratuit d'une heure "
                              "à la médiathèque du quartier.")
    note("Podcast local", "# Podcast local\nÉcouter les podcasts de la ville pour repérer "
                          "les commerçants qui bougent.")
    note("Carnet vidéo", "# Carnet vidéo\nFilmer chaque étape du projet en 30 secondes.")

    for i in range(4):  # Clients, Offre et Prix servent ensemble plusieurs jours
        cc.activer("Projet A", [clients, offre, prix], date=debut + timedelta(days=i),
                   racine=racine, acteur="demo", raison="démonstration")
    cc.activer("Projet A", [objectif, clients], date=debut, racine=racine, acteur="demo")

    projets.creer_tache("Projet A", "Écrire le texte de la page d'accueil", note_id=objectif,
                        echeance=(aujourd_hui + timedelta(days=3)).isoformat(),
                        racine=racine, acteur="demo")
    projets.creer_tache("Projet A", "Lister 10 entreprises à contacter", note_id=clients,
                        echeance=(aujourd_hui + timedelta(days=7)).isoformat(),
                        racine=racine, acteur="demo")

    redacteur = agents_mod.charger("redacteur", racine=racine, date=aujourd_hui)
    voies.proposer(redacteur, "Projet A", "note",
                   "# Slogan\nVotre site en une semaine, à prix clair.\n"
                   "Résume l'[[Offre]] pour les [[Clients cibles]].",
                   raison="idée de slogan tirée de l'offre")

    # ---------------- Projet B : projet sensible ----------------
    projets.creer_projet("Projet B", racine=racine, acteur="demo", raison="projet de démonstration")
    cc.marquer_projet_demo("Projet B", racine=racine)
    cc.marquer_projet_sensible("Projet B", racine=racine)
    noteb = lambda titre, texte: cc.creer_note_humaine("Projet B", titre, texte, sensible=True,
                                                        date=debut, racine=racine, acteur="demo")
    carnet = noteb("Carnet privé", "# Carnet privé\nNotes personnelles (fictives). "
                   "Voir [[Objectifs du trimestre]].")
    noteb("Objectifs du trimestre", "# Objectifs du trimestre\nSommeil, sport, lecture "
          "(exemple fictif). Bilan dans le [[Carnet privé]].")
    projets.creer_tache("Projet B", "Relire le carnet du mois", note_id=carnet,
                        racine=racine, acteur="demo")

    # ---------------- Une nuit de sommeil, puis un tour ----------------
    nuit = sommeil.dormir(aujourd_hui, racine=racine)
    bilan = orchestrateur.tour(aujourd_hui, racine=racine)

    if bavard:
        print("Démo créée : « Projet A » (normal) et « Projet B » (sensible).")
        print(f"- {len(bilan['actions'])} action(s) de l'orchestrateur, "
              f"{bilan['appels_ia']} appel(s) à l'IA de démonstration (0 €).")
        a = nuit["projets"].get("Projet A", {})
        print(f"- Sommeil : {len(a.get('tri_propositions', []))} proposition(s) de tri, "
              f"{len(a.get('syntheses_proposees', []))} synthèse(s), un slogan en attente.")
        from noyau import reve
        idee = reve.lister("Projet A", racine=racine)
        if idee:
            print(f"- Rêve de la nuit (score {idee[-1]['score']}/10) : {idee[-1]['idee']}")
        print("Pour voir et trier les idées rêvées : python3 jarvis.py reve")
    return True


def dossier_demo():
    """~/.jarvis/demo : à part des vrais projets."""
    from noyau import reglages
    return reglages.dossier_donnees() / "demo"


def main(argv=None):
    import argparse
    import os
    a = argparse.ArgumentParser(prog="python3 exemples/demo.py",
                                description="Démonstration de JARVIS avec de fausses données.")
    a.add_argument("--remplacer", action="store_true", help="recréer la démo de zéro")
    a.add_argument("--dossier", help="dossier de la démo (par défaut ~/.jarvis/demo)")
    a.add_argument("--port", type=int, default=8765)
    a.add_argument("--sans-interface", action="store_true", help="ne pas ouvrir l'interface")
    a.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur")
    args = a.parse_args(argv)
    dossier = Path(args.dossier).expanduser().resolve() if args.dossier else dossier_demo()
    os.environ["DOSSIER_DONNEES"] = str(dossier)   # tout ce qui suit travaille dans la démo
    os.environ.setdefault("mode_ia", "simule")     # IA simulée : aucune clé, 0 €
    print(f"Dossier de la démo : {dossier}")
    creer_demo(remplacer=args.remplacer)
    if not args.sans_interface:
        from interface import serveur_web
        serveur_web.lancer(port=args.port, ouvrir=not args.sans_navigateur)


if __name__ == "__main__":
    main()
