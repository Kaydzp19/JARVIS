"""
Fournisseurs de données RÉELLES pour l'interface (widgets et hologrammes).

Chaque fonction renvoie un petit dictionnaire prêt à être affiché, sans aucun
texte de note. Rien n'est écrit, rien n'exige les droits administrateur
(jamais de sudo). Si une mesure est impossible sur cette machine, la valeur
vaut None et l'interface affiche « indisponible ».

    machine()                 CPU, RAM, disque, batterie, processus, historique 2 min
    depenses(racine)          dépense IA : session, aujourd'hui, ce mois, 6 mois, plafond
    nuit(projet, racine)      résumé de la dernière nuit
    meteo()                   météo (seulement si METEO_LATITUDE et METEO_LONGITUDE sont réglées)
    journal_du_jour(racine)   lignes du journal d'aujourd'hui (projets sensibles masqués)

Uniquement la bibliothèque standard de Python.
"""

import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from collections import deque
from datetime import date, datetime
from pathlib import Path

from noyau import corps_calleux as cc
from noyau import projets, reglages, reve, routeur_ia, systeme

HISTORIQUE = deque(maxlen=24)          # 24 mesures toutes les 5 s = 2 minutes
_VERROU = threading.Lock()
_CPU_PRECEDENT = None
_APPELS_AU_DEMARRAGE = None


def _commande(args, delai=3):
    """Lance une commande en lecture seule. Renvoie sa sortie, ou "" si impossible."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=delai)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ------------------------------------------------------------------
# Machine
# ------------------------------------------------------------------

def _cpu_linux():
    global _CPU_PRECEDENT
    try:
        valeurs = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    except (OSError, ValueError, IndexError):
        return None
    inactif, total = valeurs[3] + (valeurs[4] if len(valeurs) > 4 else 0), sum(valeurs)
    precedent, _CPU_PRECEDENT = _CPU_PRECEDENT, (inactif, total)
    if precedent is None:
        time.sleep(0.15)
        return _cpu_linux()
    d_total = total - precedent[1]
    return round(100.0 * (1 - (inactif - precedent[0]) / d_total), 1) if d_total > 0 else 0.0


def _cpu_mac():
    m = re.search(r"([\d.]+)% idle", _commande(["top", "-l", "1", "-n", "0"], 5))
    return round(100.0 - float(m.group(1)), 1) if m else None


def cpu():
    systeme_ = platform.system()
    valeur = _cpu_linux() if systeme_ == "Linux" else _cpu_mac() if systeme_ == "Darwin" else None
    if valeur is None and hasattr(os, "getloadavg"):
        valeur = round(min(100.0, 100.0 * os.getloadavg()[0] / (os.cpu_count() or 1)), 1)
    return valeur


def ram():
    """{"utilisee_go", "totale_go", "pourcent"} ou None."""
    if platform.system() == "Linux":
        try:
            info = {l.split(":")[0]: int(l.split()[1]) for l in
                    Path("/proc/meminfo").read_text().splitlines() if l.split()[1:2]}
            total, libre = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0))
        except (OSError, KeyError, ValueError):
            return None
        total, utilisee = total / 1024 ** 2, (total - libre) / 1024 ** 2
    elif platform.system() == "Darwin":
        taille = _commande(["sysctl", "-n", "hw.memsize"]).strip()
        vm = _commande(["vm_stat"])
        page = re.search(r"page size of (\d+)", vm)
        if not (taille.isdigit() and page):
            return None
        pages = {k: int(v) for k, v in re.findall(r"Pages (\w[\w ]*?):\s+(\d+)", vm)}
        libres = pages.get("free", 0) + pages.get("inactive", 0) + pages.get("speculative", 0)
        total = int(taille) / 1024 ** 3
        utilisee = total - libres * int(page.group(1)) / 1024 ** 3
    else:
        return None
    return {"utilisee_go": round(utilisee, 1), "totale_go": round(total, 1),
            "pourcent": round(100 * utilisee / total, 1) if total else None}


def disque():
    try:
        u = shutil.disk_usage(str(Path.home()))
    except OSError:
        return None
    return {"utilise_go": round(u.used / 1024 ** 3, 1), "total_go": round(u.total / 1024 ** 3, 1),
            "pourcent": round(100 * u.used / u.total, 1)}


def batterie():
    """{"pourcent", "en_charge"} ou None (ordinateur fixe, ou mesure impossible)."""
    if platform.system() == "Darwin":
        m = re.search(r"(\d+)%;\s*([\w ]+)", _commande(["pmset", "-g", "batt"]))
        if m:
            return {"pourcent": int(m.group(1)),
                    "en_charge": m.group(2).strip() in ("charging", "charged", "finishing charge")}
        return None
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            return {"pourcent": int((bat / "capacity").read_text().strip()),
                    "en_charge": (bat / "status").read_text().strip() in ("Charging", "Full")}
        except (OSError, ValueError):
            continue
    return None


def processus(nombre=5):
    """Les processus qui utilisent le plus le processeur : NOM seulement (jamais les arguments)."""
    if platform.system() == "Darwin":
        sortie = _commande(["ps", "-Ao", "pcpu=,pmem=,comm=", "-r"])
    else:
        sortie = _commande(["ps", "-eo", "pcpu=,pmem=,comm=", "--sort=-pcpu"])
    resultat = []
    for ligne in sortie.splitlines():
        morceaux = ligne.split(None, 2)
        if len(morceaux) < 3:
            continue
        try:
            nom = morceaux[2].strip()
            resultat.append({"nom": (Path(nom).name if nom.startswith("/") else nom)[:40],
                             "cpu": float(morceaux[0].replace(",", ".")),
                             "ram": float(morceaux[1].replace(",", "."))})
        except ValueError:
            continue
        if len(resultat) >= nombre:
            break
    return resultat


def machine():
    """Toutes les mesures, plus l'historique des 2 dernières minutes (CPU et RAM)."""
    with _VERROU:
        mesure = {"cpu": cpu(), "ram": ram(), "disque": disque(), "batterie": batterie(),
                  "temperature": None,          # nécessiterait les droits administrateur
                  "processus": processus(), "heure": datetime.now().strftime("%H:%M:%S"),
                  "systeme": platform.system() or "inconnu"}
        HISTORIQUE.append({"heure": mesure["heure"], "cpu": mesure["cpu"],
                           "ram": (mesure["ram"] or {}).get("pourcent")})
        mesure["historique"] = list(HISTORIQUE)
    return mesure


# ------------------------------------------------------------------
# Dépenses IA
# ------------------------------------------------------------------

def _total_appels(racine):
    conn = systeme.connexion(racine)
    try:
        return conn.execute("SELECT COALESCE(MAX(id), 0) FROM appels_ia").fetchone()[0]
    finally:
        conn.close()


def demarrer_session(racine=None):
    """Mémorise le dernier appel IA connu au lancement : « session » = les appels suivants."""
    global _APPELS_AU_DEMARRAGE
    _APPELS_AU_DEMARRAGE = _total_appels(racine)


def _mois_precedents(n, aujourd_hui):
    mois, a, m = [], aujourd_hui.year, aujourd_hui.month
    for _ in range(n):
        mois.append(f"{a:04d}-{m:02d}")
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    return list(reversed(mois))


def depenses(racine=None, aujourd_hui=None, mois=6):
    aujourd_hui = aujourd_hui or date.today()
    conn = systeme.connexion(racine)
    try:
        par_mois = {r["mois"]: r["montant_estime"] for r in conn.execute("SELECT * FROM budget_ia")}
        jour = conn.execute("SELECT COALESCE(SUM(cout_estime), 0) FROM appels_ia WHERE date = ?",
                            (aujourd_hui.isoformat(),)).fetchone()[0]
        session = conn.execute("SELECT COALESCE(SUM(cout_estime), 0), COUNT(*) FROM appels_ia "
                               "WHERE id > ?", (_APPELS_AU_DEMARRAGE or 0,)).fetchone()
    finally:
        conn.close()
    serie = [{"mois": m, "montant": round(par_mois.get(m, 0.0), 2)}
             for m in _mois_precedents(mois, aujourd_hui)]
    return {"session": round(session[0], 3), "appels_session": session[1],
            "aujourd_hui": round(jour, 3), "mois": serie[-1]["montant"],
            "plafond": routeur_ia.plafond_mensuel(), "serie": serie, "mode_ia": routeur_ia.mode_ia()}


# ------------------------------------------------------------------
# Nuit
# ------------------------------------------------------------------

MOTIF_BILAN = re.compile(r"(\d+) renforcement\(s\), (\d+) archivage\(s\), (\d+) synthèse")


def nuit(projet, racine=None):
    """Résumé de la dernière nuit d'un projet : chiffres seulement."""
    bilan = {"projet": projet, "date": None, "renforcees": 0, "archivees": 0,
             "syntheses": 0, "idees_en_attente": 0, "propositions_en_attente": 0}
    for l in reversed(projets.lire_journal(projet, racine)):
        if l["evenement"] == "sommeil terminé" and l["raison"]:
            m = MOTIF_BILAN.search(l["raison"])
            if m:
                bilan.update(date=l["date"][:10], renforcees=int(m.group(1)),
                             archivees=int(m.group(2)), syntheses=int(m.group(3)))
            break
    bilan["idees_en_attente"] = len(reve.lister(projet, "nouvelle", racine))
    bilan["propositions_en_attente"] = len(cc.lister_propositions(projet, "en attente", racine))
    bilan["depense_mois"] = round(routeur_ia.depense_du_mois(racine=racine), 2)
    bilan["plafond"] = routeur_ia.plafond_mensuel()
    return bilan


# ------------------------------------------------------------------
# Météo (Open-Meteo, sans clé ; seulement si Kayd a réglé sa position)
# ------------------------------------------------------------------

def meteo(ouvrir=None):
    lat, lon = reglages.lire("METEO_LATITUDE"), reglages.lire("METEO_LONGITUDE")
    if not (lat and lon):
        return {"disponible": False,
                "raison": "Météo non réglée : ajoute METEO_LATITUDE et METEO_LONGITUDE "
                          "dans reglages.local."}
    try:
        lat, lon = float(lat.replace(",", ".")), float(lon.replace(",", "."))
    except ValueError:
        return {"disponible": False, "raison": "Position météo illisible dans reglages.local."}
    adresse = ("https://api.open-meteo.com/v1/forecast?latitude=%.3f&longitude=%.3f"
               "&hourly=temperature_2m,precipitation_probability&daily=weather_code,"
               "temperature_2m_max,temperature_2m_min&current=temperature_2m,weather_code"
               "&timezone=auto&forecast_days=7" % (lat, lon))
    try:
        with (ouvrir or urllib.request.urlopen)(adresse, timeout=5) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # réseau absent, service indisponible…
        return {"disponible": False, "raison": f"Météo indisponible ({type(e).__name__})."}
    h, j = d.get("hourly", {}), d.get("daily", {})
    return {
        "disponible": True,
        "actuelle": {"temperature": d.get("current", {}).get("temperature_2m"),
                     "code": d.get("current", {}).get("weather_code")},
        "heures": [{"heure": t[11:16], "temperature": v, "pluie": p} for t, v, p in
                   list(zip(h.get("time", []), h.get("temperature_2m", []),
                            h.get("precipitation_probability", [])))[:24]],
        "jours": [{"date": t, "code": c, "max": hi, "min": lo} for t, c, hi, lo in
                  zip(j.get("time", []), j.get("weather_code", []),
                      j.get("temperature_2m_max", []), j.get("temperature_2m_min", []))],
    }


# ------------------------------------------------------------------
# Journal du jour
# ------------------------------------------------------------------

def journal_du_jour(racine=None, aujourd_hui=None, limite=30):
    """Lignes du journal d'aujourd'hui, tous projets. Projets sensibles : contenu privé masqué."""
    jour = (aujourd_hui or date.today()).isoformat()
    lignes = []
    for p in cc.lister_projets(racine):
        sensible = cc.projet_sensible(p, racine)
        for l in projets.lire_journal(p, racine):
            if not l["date"].startswith(jour):
                continue
            lignes.append({"projet": p, "date": l["date"], "acteur": l["acteur"],
                           "evenement": "contenu privé masqué" if sensible else l["evenement"],
                           "prive": sensible})
    lignes.sort(key=lambda l: l["date"], reverse=True)
    return lignes[:limite]


# ------------------------------------------------------------------
# Calendrier extérieur (fourni par un module, ex. « agenda »), en lecture seule
# ------------------------------------------------------------------

def calendrier(debut, jours=7, racine=None):
    """Événements d'un calendrier extérieur, demandés aux modules actifs. Jamais d'erreur."""
    from datetime import timedelta
    from noyau import modules
    from noyau.outils import jour
    d = jour(debut)
    resultats = modules.emettre("agenda_lire", {"debut": d.isoformat(),
                                                "fin": (d + timedelta(days=int(jours))).isoformat()},
                                racine=racine)
    for r in resultats:
        if r["ok"] and isinstance(r["resultat"], dict):
            return dict(r["resultat"], module=r["module"])
    if resultats:
        return {"disponible": False, "evenements": [],
                "raison": "Agenda illisible pour l'instant : la planification continue sans lui."}
    return {"disponible": False, "evenements": [],
            "raison": "Agenda Apple non branché : python3 jarvis.py modules --activer agenda --mode REEL"}
