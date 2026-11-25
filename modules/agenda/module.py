"""
Module « agenda » : l'agenda Apple (app Calendrier), lu directement sur ce Mac.

Lecture seule pour l'instant. Les événements s'affichent dans la frise de la Planification,
dans une couleur à part, non modifiables. Option : masquer les titres (on n'affiche que
« occupé »).

Modes :
- DEMO : de faux rendez-vous, rien n'est lu sur la machine ;
- REEL : lecture locale de l'app Calendrier par AppleScript (osascript, fourni avec macOS).
  Aucun identifiant ni mot de passe : macOS demande seulement, la première fois,
  l'autorisation de laisser le Terminal accéder à Calendrier.

Écriture (créer ou déplacer un événement Apple) : PRÉPARÉE seulement. Elle devient une
proposition « À valider » ; même validée, elle n'est pas exécutée dans cette étape
(réglage agenda_ecriture, désactivé, et exécution non branchée).

Réglages facultatifs (reglages.local) :
    agenda_masquer_titres=true      affiche « occupé » au lieu des titres
    agenda_calendriers=Travail,Perso  ne lire que ces calendriers (vide = tous)

Événements écoutés :
    agenda_lire               {"debut": "AAAA-MM-JJ", "fin": "AAAA-MM-JJ"} -> événements
    agenda_preparer_ecriture  {"projet", "action": "creer"|"deplacer", "evenement": {...}}
    proposition_validee       une proposition de ce module a été validée par Kayd
"""

import platform
import shutil
import subprocess
from datetime import date, datetime, timedelta

SEP_CHAMP, SEP_LIGNE = "\x1f", "\x1e"
DELAI = 30
GUIDE_AUTORISATION = ("Autorise l'accès : Réglages Système › Confidentialité et sécurité › "
                      "Calendriers (et Automatisation › Terminal › Calendrier), puis réessaie.")


# ------------------------------------------------------------------
# Lecture
# ------------------------------------------------------------------

def _jour(d):
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def _date_applescript(nom, d):
    """Une date AppleScript construite pièce par pièce (indépendante de la langue du Mac)."""
    return (f"set {nom} to current date\n set day of {nom} to 1\n set year of {nom} to {d.year}\n"
            f" set month of {nom} to {d.month}\n set day of {nom} to {d.day}\n set time of {nom} to 0\n")


def script_lecture(debut, fin):
    """Le script AppleScript qui lit les événements entre debut (inclus) et fin (exclue)."""
    debut, fin = _jour(debut), _jour(fin)
    return (
        "on iso(d)\n"
        " set h to hours of d\n set mi to minutes of d\n"
        " return (year of d as string) & \"-\" & text -2 thru -1 of (\"0\" & ((month of d) as integer)) & \"-\" & "
        "text -2 thru -1 of (\"0\" & (day of d)) & \"T\" & text -2 thru -1 of (\"0\" & h) & \":\" & "
        "text -2 thru -1 of (\"0\" & mi)\n"
        "end iso\n"
        "on run\n"
        + _date_applescript("dDebut", debut) + _date_applescript("dFin", fin) +
        " set sep to ASCII character 31\n set fin_ligne to ASCII character 30\n set sortie to \"\"\n"
        " tell application \"Calendar\"\n"
        "  repeat with c in calendars\n"
        "   set nomC to name of c\n"
        "   try\n"
        "    set evs to (every event of c whose start date < dFin and end date > dDebut)\n"
        "    repeat with e in evs\n"
        "     set sortie to sortie & nomC & sep & (summary of e) & sep & my iso(start date of e) & sep & "
        "my iso(end date of e) & sep & (allday event of e as string) & fin_ligne\n"
        "    end repeat\n"
        "   end try\n"
        "  end repeat\n"
        " end tell\n"
        " return sortie\n"
        "end run\n")


def analyser(sortie):
    """Transforme la sortie du script en événements."""
    evenements = []
    for ligne in sortie.split(SEP_LIGNE):
        champs = ligne.strip("\n").split(SEP_CHAMP)
        if len(champs) != 5:
            continue
        calendrier, titre, debut, fin, journee = champs
        evenements.append({"calendrier": calendrier.strip(), "titre": titre.strip() or "(sans titre)",
                           "debut": debut.strip(), "fin": fin.strip(), "journee": journee.strip() == "true"})
    evenements.sort(key=lambda e: e["debut"])
    return evenements


def lire_mac(debut, fin, executer=None):
    """Lecture RÉELLE (app Calendrier). Renvoie {"disponible", "evenements", "raison"?}."""
    if executer is None:
        if platform.system() != "Darwin" or not shutil.which("osascript"):
            return {"disponible": False, "evenements": [],
                    "raison": "La lecture de l'agenda Apple ne marche que sur un Mac (app Calendrier)."}

        def executer(script):
            return subprocess.run(["osascript", "-e", script], capture_output=True, text=True,
                                  timeout=DELAI)
    try:
        r = executer(script_lecture(debut, fin))
    except subprocess.TimeoutExpired:
        return {"disponible": False, "evenements": [],
                "raison": "Calendrier met trop de temps à répondre. La planification continue sans l'agenda."}
    except OSError as e:
        return {"disponible": False, "evenements": [], "raison": f"Agenda illisible ({type(e).__name__})."}
    if r.returncode != 0:
        refus = "-1743" in r.stderr or "-1744" in r.stderr or "not allowed" in r.stderr.lower()
        return {"disponible": False, "evenements": [],
                "raison": ("Accès à Calendrier refusé. " + GUIDE_AUTORISATION) if refus
                else "Agenda illisible pour l'instant. La planification continue sans l'agenda."}
    return {"disponible": True, "evenements": analyser(r.stdout)}


def lire_demo(debut, fin):
    """De faux rendez-vous (mode DEMO), stables d'un jour à l'autre."""
    modeles = [("Travail", "Réunion d'équipe", 9, 30, 60), ("Perso", "Sport", 18, 0, 60),
               ("Perso", "Dentiste", 14, 0, 45), ("Travail", "Point client", 11, 0, 30)]
    evenements, d = [], _jour(debut)
    while d < _jour(fin):
        if d.weekday() < 5:
            cal, titre, h, m, duree = modeles[d.toordinal() % len(modeles)]
            t0 = datetime(d.year, d.month, d.day, h, m)
            t1 = t0 + timedelta(minutes=duree)
            evenements.append({"calendrier": cal, "titre": titre, "debut": t0.isoformat()[:16],
                               "fin": t1.isoformat()[:16], "journee": False})
        d += timedelta(days=1)
    return {"disponible": True, "evenements": evenements}


def _oui(valeur):
    return str(valeur).strip().lower() in ("true", "vrai", "oui", "yes", "1")


def lire(donnees, contexte, executer=None):
    debut = _jour(donnees.get("debut") or date.today())
    fin = _jour(donnees.get("fin") or debut + timedelta(days=7))
    r = lire_demo(debut, fin) if contexte.mode == "DEMO" else lire_mac(debut, fin, executer)
    filtre = [c.strip() for c in contexte.reglage("agenda_calendriers").split(",") if c.strip()]
    if filtre:
        r["evenements"] = [e for e in r["evenements"] if e["calendrier"] in filtre]
    masquer = _oui(donnees.get("masquer_titres")) or _oui(contexte.reglage("agenda_masquer_titres"))
    if masquer:
        r["evenements"] = [dict(e, titre="occupé", calendrier="") for e in r["evenements"]]
    r.update(source="démo" if contexte.mode == "DEMO" else "Calendrier (ce Mac)", masque=masquer,
             modifiable=False)
    return r


# ------------------------------------------------------------------
# Écriture : préparée, jamais exécutée sans validation (et pas dans cette étape)
# ------------------------------------------------------------------

def _texte_applescript(t):
    return '"' + str(t).replace("\\", "\\\\").replace('"', '\\"') + '"'


def script_ecriture(action, ev):
    """Le script qui créerait l'événement (préparé, non exécuté)."""
    debut = datetime.fromisoformat(ev["debut"])
    fin = datetime.fromisoformat(ev["fin"])
    dates = (_date_applescript("dDebut", debut.date()) + f" set time of dDebut to {debut.hour * 3600 + debut.minute * 60}\n"
             + _date_applescript("dFin", fin.date()) + f" set time of dFin to {fin.hour * 3600 + fin.minute * 60}\n")
    cal = _texte_applescript(ev.get("calendrier") or "Calendrier")
    if action == "creer":
        corps = (f" tell application \"Calendar\" to tell calendar {cal}\n"
                 f"  make new event with properties {{summary:{_texte_applescript(ev['titre'])}, "
                 "start date:dDebut, end date:dFin}\n end tell\n")
    else:
        corps = (f" tell application \"Calendar\" to tell calendar {cal}\n"
                 f"  set e to first event whose summary is {_texte_applescript(ev['titre'])}\n"
                 "  set start date of e to dDebut\n  set end date of e to dFin\n end tell\n")
    return "on run\n" + dates + corps + "end run\n"


def preparer_ecriture(donnees, contexte):
    """Crée une proposition « À valider ». Rien n'est écrit dans l'agenda Apple."""
    action, ev = donnees.get("action"), donnees.get("evenement") or {}
    if action not in ("creer", "deplacer"):
        raise ValueError("Action d'agenda inconnue (creer ou deplacer).")
    for cle in ("titre", "debut", "fin"):
        if not ev.get(cle):
            raise ValueError(f"Événement incomplet : {cle} manquant.")
    script = script_ecriture(action, ev)            # vérifie aussi les dates
    verbe = "Créer" if action == "creer" else "Déplacer"
    pid = contexte.proposer(
        donnees["projet"], f"Agenda Apple : {verbe.lower()} « {ev['titre']} »"[:80],
        f"{verbe} dans l'agenda Apple : {ev['titre']}, du {ev['debut']} au {ev['fin']}.\n"
        "Rien n'est écrit dans l'agenda tant que tu n'as pas validé.",
        raison="écriture dans l'agenda Apple, préparée par le module agenda",
        details={"action": action, "evenement": ev})
    return {"proposition": pid, "script_prepare": script, "execute": False}


def executer_ecriture(details, contexte):
    """Exécution d'une écriture VALIDÉE : désactivée dans cette étape."""
    if not _oui(contexte.reglage("agenda_ecriture")):
        return "non exécuté : l'écriture dans l'agenda Apple n'est pas encore activée (étape suivante)"
    raise NotImplementedError("L'écriture dans l'agenda Apple sera branchée à l'étape suivante.")


def recevoir(evenement, donnees, contexte):
    if evenement == "agenda_lire":
        return lire(donnees, contexte)
    if evenement == "agenda_preparer_ecriture":
        return preparer_ecriture(donnees, contexte)
    if evenement == "proposition_validee":
        if (donnees.get("details") or {}).get("module") != "agenda":
            return None
        return executer_ecriture(donnees["details"], contexte)
    return None
