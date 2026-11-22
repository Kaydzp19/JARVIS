"""
Sommeil de JARVIS (marche 6) : la consolidation nocturne.

Chaque nuit, pour chaque projet :
1. l'oubli est appliqué (les synapses s'affaiblissent, les liens utilisés
   ensemble la veille se renforcent, les plus faibles sont archivés) ;
2. JARVIS repère les groupes de notes très liées entre elles ;
3. l'agent « synthetiseur » propose une note de synthèse pour chaque
   nouveau groupe. Elle reste EN ATTENTE : Kayd la valide au réveil.
4. Une ligne de journal explique ce qui a été fait et pourquoi.

Sur Mac, la nuit est déclenchée par launchd (le planificateur intégré au
Mac) : voir « python3 jarvis.py installer-sommeil ». Limite : si le Mac
est éteint, rien ne tourne (résolu plus tard par le VPS, marche 8).
"""

import sys
from pathlib import Path

from noyau import agent as agents_mod
from noyau import corps_calleux, synapses
from noyau.outils import jour

REGLAGES_SOMMEIL = {
    "seuil_groupe": 0.25,      # poids minimum pour que deux notes soient « très liées »
    "taille_min_groupe": 3,    # nombre minimum de notes pour proposer une synthèse
}


def trouver_groupes(projet, racine=None, reglages=None):
    """Groupes de notes reliées par des synapses fortes (composantes connexes)."""
    r = dict(REGLAGES_SOMMEIL, **(reglages or {}))
    parent = {}

    def chef(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    poids = {}
    for s in synapses.lister_synapses(projet, racine, avec_archivees=False):
        if s["poids"] >= r["seuil_groupe"]:
            a, b = s["note_source"], s["note_cible"]
            parent[chef(a)] = chef(b)
            poids.setdefault(a, []).append(s["poids"])
            poids.setdefault(b, []).append(s["poids"])
    groupes = {}
    for n in list(parent):
        groupes.setdefault(chef(n), []).append(n)
    resultat = []
    for membres in groupes.values():
        if len(membres) >= r["taille_min_groupe"]:
            tous = [p for m in membres for p in poids.get(m, [])]
            resultat.append({"notes": sorted(membres),
                             "poids_moyen": round(sum(tous) / len(tous), 3)})
    return sorted(resultat, key=lambda g: g["notes"])


def _deja_propose(projet, signature, racine):
    marque = f"groupe {signature}"
    return any(p["type"] == "synthese" and marque in (p["raison"] or "")
               for p in corps_calleux.lister_propositions(projet, racine=racine))


def dormir(date=None, racine=None, reglages=None):
    date = jour(date)
    synthetiseur = agents_mod.charger("synthetiseur", racine=racine, date=date)
    bilan = {"date": date.isoformat(), "projets": {}}
    for projet in corps_calleux.lister_projets(racine):
        oubli = synapses.appliquer_oubli(projet, date, racine=racine)
        notes = {n["id"]: n for n in corps_calleux.se_souvenir(projet, "", 50, racine=racine)}
        sensible_projet = corps_calleux.projet_sensible(projet, racine)
        proposees = []
        for g in trouver_groupes(projet, racine, reglages):
            signature = ",".join(str(i) for i in g["notes"])
            if _deja_propose(projet, signature, racine):
                continue
            membres = [notes[i] for i in g["notes"] if i in notes]
            titres = [m["titre"] for m in membres]
            sensible = sensible_projet or any(m["sensible"] for m in membres)
            texte = "\n".join(f"{m['titre']} : {m['extrait']}" for m in membres)
            reponse = synthetiseur.ia("synthetiser", texte, "courante", sensible)
            contenu = (f"# Synthèse : {', '.join(titres)}\n\n{reponse['reponse']}\n\n"
                       "Notes regroupées :\n" + "\n".join(f"- [[{t}]]" for t in titres) + "\n")
            raison = (f"groupe {signature} : {len(titres)} notes très liées "
                      f"(poids moyen {g['poids_moyen']:.2f}) repérées pendant le sommeil")
            pid = synthetiseur.proposer(projet, "synthese", contenu, liens=titres,
                                        titre=f"Synthèse : {', '.join(titres)}"[:80],
                                        raison=raison)
            proposees.append(pid)
        corps_calleux.journal(
            projet, "sommeil terminé",
            f"{oubli['renforcees']} renforcement(s), {oubli['archivees']} archivage(s), "
            f"{len(proposees)} synthèse(s) proposée(s)",
            date=date, racine=racine, acteur="sommeil")
        bilan["projets"][projet] = dict(oubli, syntheses_proposees=proposees)
    return bilan


# ------------------------------------------------------------------
# Planification sur Mac (launchd)
# ------------------------------------------------------------------

ETIQUETTE = "com.jarvis.sommeil"


def plist_launchd(chemin_depot, dossier_donnees, python=None, heure=3, minute=30):
    """Le fichier de réglage launchd qui lance « jarvis.py dormir » chaque nuit."""
    python = python or sys.executable
    depot = Path(chemin_depot)
    journal = Path(dossier_donnees) / "sommeil.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{ETIQUETTE}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{depot / 'jarvis.py'}</string>
        <string>dormir</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{depot}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{heure}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{journal}</string>
    <key>StandardErrorPath</key>
    <string>{journal}</string>
</dict>
</plist>
"""
