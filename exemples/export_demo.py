"""
Construit le site de la démo en ligne (site statique, ex. Vercel) :

    python3 exemples/export_demo.py

- vercel-demo/index.html : le cockpit (interface/sphere/index.html), en mode « démo en
  ligne » : fausses données calculées dans le navigateur, aucun serveur, rien n'est enregistré ;
- vercel-demo/sphere/ : ses fichiers (CSS, JavaScript, catalogue des hologrammes).

Aucune donnée réelle, aucun chemin local, aucune clé : seulement le code de l'interface.
"""

import shutil
import sys
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent
DOSSIER_SITE = RACINE_DEPOT / "vercel-demo"
SOURCE_SPHERE = RACINE_DEPOT / "interface" / "sphere"
GENERE = "<!-- Page GÉNÉRÉE par exemples/export_demo.py à partir de interface/sphere/ : ne pas la modifier à la main. -->"


def fichiers_sphere():
    """Les fichiers publiés de l'interface (sans les tests). Chemins relatifs à interface/sphere/."""
    return sorted(f.relative_to(SOURCE_SPHERE) for f in SOURCE_SPHERE.rglob("*")
                  if f.is_file() and "tests" not in f.relative_to(SOURCE_SPHERE).parts
                  and f.suffix in (".html", ".css", ".js"))


def page_sphere_en_ligne(html):
    """La page de l'interface, en mode « démo en ligne » (pas de serveur)."""
    remplacements = [
        ('<body data-page="interface">', '<body data-page="interface" data-mode="demo-en-ligne">'),
        ('<body data-page="catalogue">', '<body data-page="catalogue" data-mode="demo-en-ligne">'),
        ("<title>JARVIS · Second cerveau</title>", "<title>JARVIS · Démo en ligne</title>"),
    ]
    for avant, apres in remplacements:
        html = html.replace(avant, apres, 1)
    if 'data-mode="demo-en-ligne"' not in html:
        raise RuntimeError("Interface inattendue : <body data-page=…> introuvable.")
    return html.replace("<!doctype html>", "<!doctype html>\n" + GENERE, 1)


def construire_sphere(destination=None):
    """Copie interface/sphere/ dans le site : index.html + sphere/ (CSS, JS, catalogue)."""
    destination = Path(destination or DOSSIER_SITE)
    cible = destination / "sphere"
    if cible.exists():
        shutil.rmtree(cible)
    for rel in fichiers_sphere():
        f = cible / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        texte = (SOURCE_SPHERE / rel).read_text(encoding="utf-8")
        f.write_text(page_sphere_en_ligne(texte) if rel.suffix == ".html" else texte, encoding="utf-8")
    index = destination / "index.html"
    index.write_text(page_sphere_en_ligne((SOURCE_SPHERE / "index.html").read_text(encoding="utf-8")),
                     encoding="utf-8")
    (cible / "index.html").unlink()          # la page d'accueil du site suffit
    return index


if __name__ == "__main__":
    sys.path.insert(0, str(RACINE_DEPOT))
    print("Site construit : " + str(construire_sphere().relative_to(RACINE_DEPOT)))
