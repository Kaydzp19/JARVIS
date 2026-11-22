#!/usr/bin/env python3
"""
JARVIS : la commande principale (la « télécommande »).

Exemples (depuis le dossier du dépôt) :
    python3 jarvis.py demo         crée les projets de démonstration Demo-A et Demo-B
    python3 jarvis.py cockpit      ouvre le cockpit web (cerveau 3D, tâches, propositions)
    python3 jarvis.py maintenant   affiche ce qu'il faut faire maintenant
    python3 jarvis.py tour         un tour de l'orchestrateur (observer, décider, agir, mesurer)
    python3 jarvis.py dormir       le sommeil : oubli + propositions de synthèse
    python3 jarvis.py propositions liste les propositions en attente
    python3 jarvis.py valider Demo-A 3     valide la proposition 3 du projet Demo-A
    python3 jarvis.py refuser Demo-A 3     refuse la proposition 3
    python3 jarvis.py modules      liste les modules ; activer / retirer avec --activer / --retirer
    python3 jarvis.py mcp          serveur MCP (lancé par Claude Desktop, pas à la main)
    python3 jarvis.py tests        lance tous les tests

Option commune : --dossier CHEMIN pour utiliser un autre dossier de données
que ~/.jarvis (par exemple pour essayer sans toucher à ses vraies données).
"""

import argparse
import json
import os
import sys
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE_DEPOT))


def _afficher(objet):
    print(json.dumps(objet, ensure_ascii=False, indent=2))


def cmd_mcp(args):
    from noyau import serveur_mcp
    serveur_mcp.servir()


def cmd_demo(args):
    sys.path.insert(0, str(RACINE_DEPOT / "exemples"))
    import demo
    demo.creer_demo(remplacer=args.remplacer)


def cmd_cockpit(args):
    from interface import serveur_web
    serveur_web.lancer(port=args.port, ouvrir=not args.sans_navigateur)


def cmd_maintenant(args):
    from noyau import orchestrateur
    action = orchestrateur.prochaine_action()
    if action is None:
        print("Rien à faire pour l'instant. Lance « python3 jarvis.py tour » si tu as ajouté des tâches.")
    else:
        print(orchestrateur.contrat_en_texte(action))


def cmd_tour(args):
    from noyau import orchestrateur
    _afficher(orchestrateur.tour())


def cmd_dormir(args):
    from noyau import sommeil
    _afficher(sommeil.dormir(args.date))


def cmd_propositions(args):
    from noyau import corps_calleux as cc
    for projet in cc.lister_projets():
        for p in cc.lister_propositions(projet, "en attente"):
            verif = p["verification"]
            etat = "non vérifiée" if not verif else ("vérifiée OK" if verif["ok"]
                                                       else "à corriger : " + "; ".join(verif["problemes"]))
            print(f"[{projet}] n°{p['id']} ({p['type']}) {p['titre']} — {etat}")
            print("    " + p["contenu"][:200].replace("\n", "\n    "))


def cmd_valider(args):
    from noyau import corps_calleux as cc
    resultat = cc.valider_proposition(args.projet, args.id)
    print(f"Proposition {args.id} validée et écrite (élément n°{resultat}).")


def cmd_refuser(args):
    from noyau import corps_calleux as cc
    cc.refuser_proposition(args.projet, args.id, raison=args.raison)
    print(f"Proposition {args.id} refusée. Rien n'a été écrit.")


def cmd_modules(args):
    from noyau import modules
    if args.activer:
        modules.activer(args.activer, mode=args.mode)
        print(f"Module « {args.activer} » activé en mode {args.mode}.")
    if args.retirer:
        modules.desactiver(args.retirer)
        print(f"Module « {args.retirer} » retiré.")
    for m in modules.decouvrir():
        etat = modules.etat(m["nom"])
        print(f"- {m['nom']} : {m.get('description', '')} "
              f"[{'actif, mode ' + etat['mode'] if etat['actif'] else 'inactif'}]")


def cmd_tests(args):
    import unittest
    suite = unittest.defaultTestLoader.discover(str(RACINE_DEPOT), top_level_dir=str(RACINE_DEPOT))
    resultat = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if resultat.wasSuccessful() else 1)


def main(argv=None):
    p = argparse.ArgumentParser(prog="jarvis", description="JARVIS, second cerveau personnel.")
    p.add_argument("--dossier", help="dossier de données (par défaut ~/.jarvis)")
    sous = p.add_subparsers(dest="commande", required=True)

    sous.add_parser("mcp", help="serveur MCP pour Claude").set_defaults(f=cmd_mcp)
    s = sous.add_parser("demo", help="créer les projets de démonstration")
    s.add_argument("--remplacer", action="store_true", help="recréer la démo de zéro")
    s.set_defaults(f=cmd_demo)
    s = sous.add_parser("cockpit", help="ouvrir le cockpit web")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--sans-navigateur", action="store_true")
    s.set_defaults(f=cmd_cockpit)
    sous.add_parser("maintenant", help="la prochaine action").set_defaults(f=cmd_maintenant)
    sous.add_parser("tour", help="un tour de l'orchestrateur").set_defaults(f=cmd_tour)
    s = sous.add_parser("dormir", help="le sommeil (oubli + synthèses)")
    s.add_argument("--date", help="date simulée AAAA-MM-JJ (par défaut aujourd'hui)")
    s.set_defaults(f=cmd_dormir)
    sous.add_parser("propositions", help="propositions en attente").set_defaults(f=cmd_propositions)
    for nom, f in (("valider", cmd_valider), ("refuser", cmd_refuser)):
        s = sous.add_parser(nom, help=f"{nom} une proposition")
        s.add_argument("projet")
        s.add_argument("id", type=int)
        if nom == "refuser":
            s.add_argument("--raison")
        s.set_defaults(f=f)
    s = sous.add_parser("modules", help="lister, activer ou retirer des modules")
    s.add_argument("--activer")
    s.add_argument("--retirer")
    s.add_argument("--mode", default="DEMO", choices=["DEMO", "REEL"])
    s.set_defaults(f=cmd_modules)
    sous.add_parser("tests", help="lancer tous les tests").set_defaults(f=cmd_tests)

    args = p.parse_args(argv)
    if args.dossier:
        os.environ["DOSSIER_DONNEES"] = str(Path(args.dossier).expanduser().resolve())
    args.f(args)


if __name__ == "__main__":
    main()
