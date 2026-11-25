"""
Export de la démo pour la version en ligne (site statique, ex. Vercel).

    python3 exemples/export_demo.py

1. Fait tourner la démo complète dans un dossier TEMPORAIRE (jamais ~/.jarvis) :
   2 projets fictifs, notes liées et validées, une nuit de sommeil, les 4 voies
   d'agents, une proposition validée, une lecture par le corps calleux (MCP).
2. Exporte dans vercel-demo/data/ des fichiers JSON qui ne contiennent QUE des
   titres, des liens, des poids, des statuts et le journal : jamais le texte des
   notes, jamais de chemin local, jamais de clé.
3. Construit le site :
   - vercel-demo/index.html : l'interface « sphère » (interface/sphere/), en mode démo
     forcé : fausses données calculées dans le navigateur, sans serveur ;
   - vercel-demo/sphere/ : ses fichiers (CSS, JavaScript, catalogue des hologrammes) ;
   - vercel-demo/cockpit.html : l'ancien cockpit (interface/cockpit.html), qui lit les JSON.
"""

import json
import os
import re
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE_DEPOT))
sys.path.insert(0, str(RACINE_DEPOT / "exemples"))

DOSSIER_SITE = RACINE_DEPOT / "vercel-demo"
DOSSIER_DONNEES_SITE = DOSSIER_SITE / "data"
CONTENU_MASQUE = "(Contenu non publié dans la démo en ligne : seuls les titres et les liens le sont.)"


def nom_fichier(projet):
    """« Projet A » -> projet-a.json"""
    return re.sub(r"[^a-z0-9]+", "-", projet.lower()).strip("-") + ".json"


def _usages(projet, racine):
    """Jours où chaque synapse a servi (pour l'apprentissage), à partir de la dernière nuit calculée."""
    from noyau import projets
    conn = projets._connexion(projet, racine)
    try:
        lignes = conn.execute(
            "SELECT u.synapse_id, u.jour FROM usages_synapses u JOIN synapses s ON s.id = u.synapse_id "
            "WHERE u.jour >= s.oubli_calcule_jusqu_au ORDER BY u.jour").fetchall()
    finally:
        conn.close()
    usages = {}
    for r in lignes:
        usages.setdefault(r["synapse_id"], []).append(r["jour"])
    return usages


def exporter_projet(projet, racine):
    """Toutes les données d'UN projet, sans aucun texte de note."""
    from interface import serveur_web
    from noyau import corps_calleux as cc
    from noyau import projets, reve, synapses

    notes = [{"id": n["id"], "titre": n["titre"], "validee": bool(n["validee"]),
              "sensible": bool(n["sensible"])} for n in projets.lister_notes(projet, racine)]
    usages = _usages(projet, racine)
    syn = [{"id": s["id"], "a": s["note_source"], "b": s["note_cible"], "poids": s["poids"],
            "archivee": bool(s["archivee"]), "jusqu_au": s["oubli_calcule_jusqu_au"],
            "activations": s["activations"], "usages": usages.get(s["id"], [])}
           for s in synapses.lister_synapses(projet, racine)]
    etat = serveur_web.etat(racine, projet)
    taches = [{"id": t["id"], "titre": t["titre"], "statut": t["statut"], "echeance": t["echeance"],
               "note_id": t["note_id"], "contrat": t["contrat"]}
              for t in cc.etat_projet(projet, racine)["taches"]]
    propositions = [{"id": p["id"], "type": p["type"], "titre": p["titre"], "statut": p["statut"],
                     "acteur": p["acteur"], "raison": p["raison"], "liens": p["liens"],
                     "note_cible": p.get("note_cible"), "verification": p["verification"],
                     "creee_le": p["creee_le"]}
                    for p in cc.lister_propositions(projet, racine=racine)]
    reves = [{k: r[k] for k in ("id", "date", "idee", "sources", "sources_titres", "score",
                                "statut", "raison")} for r in reve.lister(projet, racine=racine)]
    journal = [{"n": l["n"], "date": l["date"], "acteur": l["acteur"],
                "evenement": l["evenement"], "raison": l["raison"]}
               for l in projets.lire_journal(projet, racine)]
    return {
        "projet": projet,
        "sensible": cc.projet_sensible(projet, racine),
        "demo": True,
        "notes": notes,
        "synapses": syn,
        "taches": taches,
        "propositions": propositions,
        "reves": reves,
        "journal": journal,
        "agents": [{k: a[k] for k in ("nom", "voie", "consigne", "outils")} for a in etat["agents"]],
        "reglages": {k: synapses.REGLAGES[k] for k in ("poids_initial", "apprentissage", "oubli",
                                                        "plafond", "seuil_archivage")},
    }


def preparer_demo(racine):
    """Fait tourner la démo complète dans « racine » (un dossier temporaire)."""
    import demo
    from noyau import corps_calleux as cc
    from noyau import projets, synapses
    from noyau.outils import jour

    demo.creer_demo(racine=racine, bavard=False)
    slogan = next(p for p in cc.lister_propositions("Projet A", "en attente", racine=racine)
                  if p["titre"] == "Slogan")
    cc.valider_proposition("Projet A", slogan["id"], racine=racine)      # garde d'écriture
    demo.interroger_par_mcp(racine)                                     # corps calleux (MCP)
    # Pour que « Simuler une nuit » montre aussi l'apprentissage en ligne : les notes
    # Clients cibles, Offre et Prix « servent ensemble » les deux prochains jours.
    titres = {n["titre"]: n["id"] for n in projets.lister_notes("Projet A", racine)}
    ids = [titres[t] for t in ("Clients cibles", "Offre", "Prix")]
    depart = synapses.prochaine_nuit("Projet A", racine) - timedelta(days=1)
    for i in range(2):
        cc.activer("Projet A", ids, date=jour(depart + timedelta(days=i)), racine=racine,
                   acteur="demo", raison="usage prévu pour la démo en ligne")


def exporter(destination=None, bavard=True):
    """Lance la démo dans un dossier temporaire et écrit les JSON. Renvoie la liste des fichiers."""
    destination = Path(destination or DOSSIER_DONNEES_SITE)
    destination.mkdir(parents=True, exist_ok=True)
    anciens = dict(os.environ)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.environ["DOSSIER_DONNEES"] = tmp
            os.environ["JARVIS_REGLAGES"] = str(Path(tmp) / "reglages.local")
            os.environ["mode_ia"] = "simule"
            from noyau import projets
            preparer_demo(tmp)
            liste, fichiers = [], []
            for p in projets.lister_projets(tmp):
                donnees = exporter_projet(p, tmp)
                f = destination / nom_fichier(p)
                f.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
                fichiers.append(f)
                liste.append({"nom": p, "fichier": f.name, "sensible": donnees["sensible"],
                              "notes": len(donnees["notes"])})
            index = destination / "projets.json"
            index.write_text(json.dumps({"projets": liste, "mode_ia": "simule",
                                         "budget": {"depense": 0, "plafond": 5.0}},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
            fichiers.insert(0, index)
        finally:
            os.environ.clear()
            os.environ.update(anciens)
    if bavard:
        print("Données de démo exportées :")
        for f in fichiers:
            print("   " + str(f.relative_to(RACINE_DEPOT)) if RACINE_DEPOT in f.parents else "   " + f.name)
    return fichiers


# ------------------------------------------------------------------
# La page du site : l'interface du vrai JARVIS, branchée sur les JSON
# ------------------------------------------------------------------

BANDEAU = ('<div class="bandeau-demo" role="note"><b>Démo en ligne</b> : données fictives, '
           'rien n\'est enregistré</div>')

STYLE_BANDEAU = """
  /* --- Démo en ligne : bandeau fixe --- */
  .bandeau-demo { position: fixed; top: 0; left: 0; right: 0; height: 28px; z-index: 40; display: flex;
    align-items: center; justify-content: center; gap: 6px; background: #071a2c;
    border-bottom: 1px solid rgba(92, 225, 255, .35); color: #E6F7FF; font: 500 11px/1 var(--mono);
    letter-spacing: .06em; }
  .bandeau-demo b { color: #5CE1FF; font-weight: 600; }
  .barre { top: 28px; }
  .menu { top: calc(var(--barre) + 28px); }
  main { top: calc(var(--barre) + 28px); }
  @media (max-width: 860px) {
    .bandeau-demo { top: auto; bottom: calc(46px + env(safe-area-inset-bottom)); height: auto; padding: 6px 10px;
      font-size: 10px; border-bottom: 0; border-top: 1px solid rgba(92, 225, 255, .35); }
    .barre { top: 0; }
    main { padding-bottom: 104px; }
  }
"""


def construire_page(source=None, destination=None):
    """Copie interface/cockpit.html en version en ligne : bandeau, et serveur remplacé par js/demo.js."""
    source = Path(source or RACINE_DEPOT / "interface" / "cockpit.html")
    destination = Path(destination or DOSSIER_SITE / "cockpit.html")
    html = source.read_text(encoding="utf-8")
    remplacements = [
        ("<title>JARVIS · Second cerveau</title>", "<title>JARVIS · Démo en ligne</title>"),
        ("</style>", STYLE_BANDEAU + "</style>"),
        ("<body>", "<body>\n" + BANDEAU),
        ('<span class="puce noyau"><i></i>Noyau en ligne</span>',
         '<span class="puce noyau"><i></i>Sans serveur</span>'),
        ("« Simuler une nuit » : une vraie nuit, accélérée, sur les données de démo.",
         "En ligne, « Simuler une nuit » recalcule les synapses dans ton navigateur : "
         "oubli 0,02, apprentissage 0,10, archivage sous 0,05."),
        ('<script type="module">',
         '<script src="js/simulation.js"></script>\n<script src="js/demo.js"></script>\n'
         '<script type="module">'),
    ]
    for avant, apres in remplacements:
        if avant not in html:
            raise RuntimeError(f"Interface inattendue : « {avant} » introuvable.")
        html = html.replace(avant, apres, 1)
    html = html.replace("<!doctype html>", "<!doctype html>\n<!-- Page GÉNÉRÉE par exemples/export_demo.py "
                        "à partir de interface/cockpit.html : ne pas la modifier à la main. -->", 1)
    destination.write_text(html, encoding="utf-8")
    return destination


# ------------------------------------------------------------------
# L'interface « sphère » en ligne (aucun serveur : démo dans le navigateur)
# ------------------------------------------------------------------

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
    """Copie interface/sphere/ dans le site : index.html (sphère) + sphere/ (CSS, JS, catalogue)."""
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
    exporter()
    print("Page construite : " + str(construire_page().relative_to(RACINE_DEPOT)))
    print("Interface construite : " + str(construire_sphere().relative_to(RACINE_DEPOT)))
