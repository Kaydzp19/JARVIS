"""
Garde d'écriture : la validation HUMAINE d'une proposition.

Rien n'est écrit dans tes notes sans ta validation. Depuis le dossier du dépôt :

    python3 -m noyau.valider                       liste les propositions en attente
    python3 -m noyau.valider "Projet A:3"          valide la proposition 3 du Projet A
    python3 -m noyau.valider 3                     idem, si le numéro 3 n'existe que dans un projet
    python3 -m noyau.valider "Projet A:3" --refuser "pas utile"   refuse (rien n'est écrit)

Option --dossier CHEMIN : un autre dossier de données que ~/.jarvis (ex. la démo).
"""

import argparse
import os
import sys
from pathlib import Path

from noyau import corps_calleux as cc


def en_attente(racine=None):
    """Toutes les propositions en attente, tous projets confondus : [(projet, proposition)]."""
    return [(p, prop) for p in cc.lister_projets(racine)
            for prop in cc.lister_propositions(p, "en attente", racine)]


def trouver(identifiant, racine=None):
    """« Projet A:3 » ou « 3 » (si le numéro n'existe que dans un projet). Renvoie (projet, id)."""
    texte = str(identifiant).strip()
    if ":" in texte:
        projet, num = texte.rsplit(":", 1)
        projet, pid = projet.strip(), int(num)
        cc.lire_proposition(projet, pid, racine)  # KeyError si absente
        return projet, pid
    pid = int(texte)
    projets = [p for p in cc.lister_projets(racine)
               if any(x["id"] == pid for x in cc.lister_propositions(p, racine=racine))]
    if not projets:
        raise KeyError(f"Aucune proposition n°{pid}.")
    if len(projets) > 1:
        raise KeyError(f"La proposition n°{pid} existe dans plusieurs projets "
                       f"({', '.join(projets)}) : précise, par exemple « {projets[0]}:{pid} ».")
    return projets[0], pid


def main(argv=None, sortie=None):
    sortie = sortie or sys.stdout
    a = argparse.ArgumentParser(prog="python3 -m noyau.valider",
                                description="Valider (ou refuser) une proposition de JARVIS.")
    a.add_argument("id", nargs="?", help="« Projet A:3 », ou « 3 » si le numéro est unique")
    a.add_argument("--refuser", metavar="RAISON", nargs="?", const="",
                   help="refuser au lieu de valider (raison facultative)")
    a.add_argument("--dossier", help="dossier de données (par défaut ~/.jarvis)")
    args = a.parse_args(argv)
    if args.dossier:
        os.environ["DOSSIER_DONNEES"] = str(Path(args.dossier).expanduser().resolve())

    if not args.id:
        liste = en_attente()
        if not liste:
            print("Aucune proposition en attente.", file=sortie)
        for projet, p in liste:
            v = p["verification"]
            etat = ("non vérifiée" if not v else "vérifiée" if v["ok"]
                    else "à corriger : " + "; ".join(v["problemes"]))
            print(f"[{projet}:{p['id']}] ({p['type']}) {p['titre']} — {etat}", file=sortie)
            print("    " + p["contenu"][:200].replace("\n", "\n    "), file=sortie)
        if liste:
            print('Pour valider : python3 -m noyau.valider "Projet:numéro"', file=sortie)
        return 0

    try:
        projet, pid = trouver(args.id)
        if args.refuser is not None:
            cc.refuser_proposition(projet, pid, raison=args.refuser or None)
            print(f"Proposition {projet}:{pid} refusée. Rien n'a été écrit.", file=sortie)
        else:
            cree = cc.valider_proposition(projet, pid)
            print(f"Proposition {projet}:{pid} validée et écrite (élément n°{cree}).", file=sortie)
        return 0
    except (KeyError, ValueError) as e:
        print(f"Impossible : {e}", file=sortie)
        return 1


if __name__ == "__main__":
    sys.exit(main())
