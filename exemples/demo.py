"""
Démonstration de JARVIS (fausses données, rien de personnel, IA simulée, 0 €).

    python3 exemples/demo.py               crée la démo puis ouvre l'interface
    python3 exemples/demo.py --remplacer   la recrée de zéro

Ce que fait la démo, dans l'ordre :
  1. crée 2 projets fictifs : « Projet A » (normal) et « Projet B » (sensible) ;
  2. écrit et VALIDE des notes, relie certaines par des [[liens]] ;
  3. simule quelques jours d'usage, puis lance une nuit (tri, analyse, rêve, réveil) ;
  4. génère des propositions (slogan, tri, synthèse) qui attendent ta validation ;
  5. ouvre le cockpit (la sphère, la conversation, les widgets) dans ton navigateur.

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

    # Pour la voie « vérifier » : un lien vers une note qui n'existe pas encore.
    note("Partenaires", "# Partenaires\nDemander des devis. Voir [[Fournisseurs]] (note à écrire).")
    # Pour la voie « planifier » : le Projet B a fini sa seule tâche.
    tache_b = projets.lister_taches("Projet B", racine=racine)[0]["id"]
    orchestrateur.terminer("Projet B", tache_b, True, date=debut, racine=racine)

    # ---------------- Une nuit de sommeil, puis l'orchestrateur ----------------
    nuit = sommeil.dormir(aujourd_hui, racine=racine)
    tour1 = orchestrateur.tour(aujourd_hui, racine=racine)   # agents des 4 voies
    tour2 = orchestrateur.tour(aujourd_hui, racine=racine)   # vérification des nouvelles propositions

    # Planification : quelques tâches datées, et l'agenda Apple en mode DÉMO (faux rendez-vous).
    from noyau import modules, planification
    j = lambda n: (aujourd_hui + timedelta(days=n)).isoformat()
    for champs in ({"titre": "Appeler deux commerçants", "date": j(0), "heure": "10:00", "duree": 30,
                    "priorite": "haute", "note_id": clients},
                   {"titre": "Point hebdo du projet", "date": j(1), "heure": "09:00", "duree": 45,
                    "recurrence": "hebdomadaire", "rappel": 15},
                   {"titre": "Mettre à jour les prix", "date": j(2), "heure": "14:30", "duree": 60,
                    "note_id": prix},
                   {"titre": "Relire l'offre", "date": j(3), "heure": "16:00", "duree": 30, "note_id": offre}):
        planification.creer("Projet A", champs, racine=racine, acteur="demo")
    try:
        modules.activer("agenda", "DEMO", racine=racine)
    except KeyError:
        pass  # module retiré : la planification marche sans lui

    if bavard:
        print("1. Mémoire : « Projet A » (normal) et « Projet B » (sensible), notes liées et validées.")
        a = nuit["projets"].get("Projet A", {})
        from noyau import reve
        idee = reve.lister("Projet A", racine=racine)
        print(f"2. Nuit de sommeil : {len(a.get('tri_propositions', []))} proposition(s) de tri, "
              f"{len(a.get('syntheses_proposees', []))} synthèse(s)"
              + (f", idée rêvée (score {idee[-1]['score']}/10) : {idee[-1]['idee']}" if idee else ""))
        print(f"3. Orchestrateur : {len(tour1['actions']) + len(tour2['actions'])} action(s), "
              f"{tour1['appels_ia'] + tour2['appels_ia']} appel(s) à l'IA simulée (0 €).")
        par_voie = propositions_par_voie(racine)
        print("   Propositions par voie d'agent : "
              + ", ".join(f"{v} {n}" for v, n in par_voie.items()))
    return True


VOIES_DES_AGENTS = {"agent:planificateur": "planifier", "agent:redacteur": "proposer",
                    "agent:synthetiseur": "proposer", "agent:comparateur": "comparer",
                    "agent:verificateur": "vérifier"}


def propositions_par_voie(racine=None):
    compte = {"planifier": 0, "proposer": 0, "comparer": 0, "vérifier": 0}
    for p in PROJETS_DEMO:
        for x in cc.lister_propositions(p, racine=racine):
            voie = VOIES_DES_AGENTS.get(x["acteur"])
            if voie:
                compte[voie] += 1
    return compte


def valider_par_la_commande(dossier):
    """Étape 4 : une proposition validée avec la vraie commande humaine."""
    import subprocess
    slogan = next((x for x in cc.lister_propositions("Projet A", "en attente")
                   if x["titre"] == "Slogan"), None)
    if slogan is None:
        return None
    commande = [sys.executable, "-m", "noyau.valider", "--dossier", str(dossier),
                f"Projet A:{slogan['id']}"]
    r = subprocess.run(commande, cwd=str(Path(__file__).resolve().parent.parent),
                       capture_output=True, text=True, timeout=60)
    print(f'4. Garde d\'écriture : python3 -m noyau.valider "Projet A:{slogan["id"]}"')
    print("   " + (r.stdout.strip() or r.stderr.strip()))
    return r.returncode


def interroger_par_mcp(dossier):
    """Étape 5 : le corps calleux, interrogé par un vrai client MCP (comme Claude)."""
    from noyau.client_mcp import ClientMCP
    with ClientMCP(dossier=dossier) as c:
        outils = c.outils()
        r = c.appeler("se_souvenir", projet="Projet A", requete="prix clair", limite=3)
        c.appeler("journal", projet="Projet A", evenement="démo : mémoire lue par MCP",
                  raison="vérification de bout en bout")
    print(f"5. Corps calleux (MCP) : outils {', '.join(outils)} ; "
          f"se_souvenir(« prix clair ») -> {', '.join(x['titre'] for x in r)}")
    return r


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
    cree = creer_demo(remplacer=args.remplacer)
    if cree:
        valider_par_la_commande(dossier)
    interroger_par_mcp(dossier)
    if not args.sans_interface:
        print("6. Cockpit : la sphère, la conversation et les widgets (Ctrl + C pour arrêter).")
        from interface import serveur_web
        serveur_web.lancer(port=args.port, ouvrir=not args.sans_navigateur)


if __name__ == "__main__":
    main()
