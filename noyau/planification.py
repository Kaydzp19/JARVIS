"""
Planification (marche 7) : les prochaines tâches de Kayd, projet par projet.

Une tâche : titre, date, heure, durée, priorité, récurrence, rappel, note liée.
Statuts : « à faire », « fait », « pas fait » (le contrat d'action).

    creer(projet, champs)          ACTION HUMAINE : Kayd crée, c'est enregistré directement
    modifier(projet, id, champs)   ACTION HUMAINE (aussi : déplacer = changer date / heure)
    supprimer(projet, id)          ACTION HUMAINE
    terminer(projet, id, fait)     ACTION HUMAINE : Fait / Pas fait
                                   (tâche récurrente : passe à la prochaine occurrence)
    proposer(projet, champs)       JARVIS ne crée rien : il PROPOSE, la tâche passe par
                                   « À valider » (garde d'écriture)
    lister(projet, debut, jours)   les tâches (et leurs occurrences) d'une période
    prochaines(projet, nombre)     les prochaines tâches à faire
    donnees(projet, …)             les données d'un affichage « planification »

Chaque changement est journalisé dans le projet. Un seul projet à la fois (étanchéité) ;
« * » = vue transversale de tous les projets, en LECTURE SEULE.
Générique : rien ici n'est propre à un domaine ; l'agenda Apple est un module.
"""

import calendar
import re
from datetime import date as date_, datetime, timedelta

from noyau import corps_calleux, projets
from noyau.outils import jour

TOUS = "*"
STATUTS = ("à faire", "fait", "pas fait")
PRIORITES = ("basse", "normale", "haute")
RECURRENCES = ("aucune", "quotidienne", "jours_ouvres", "hebdomadaire", "mensuelle")
MOTIF_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CHAMPS = ("titre", "date", "heure", "duree", "priorite", "recurrence", "rappel", "note_id")


class TacheInvalide(ValueError):
    """Les champs d'une tâche ne sont pas acceptables."""


# ------------------------------------------------------------------
# Récurrence
# ------------------------------------------------------------------

def _plus_mois(d, n, jour_ancre):
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return date_(a, m, min(jour_ancre, calendar.monthrange(a, m)[1]))


def suite(ancre, recurrence):
    """Les dates successives d'une tâche récurrente, à partir de sa date d'ancrage."""
    d = jour(ancre)
    if recurrence == "aucune":
        yield d
        return
    if recurrence == "mensuelle":
        n = 0
        while True:
            yield _plus_mois(d, n, d.day)   # le 31 reste le 31 (ou le dernier jour du mois)
            n += 1
    pas = {"quotidienne": 1, "hebdomadaire": 7, "jours_ouvres": 1}[recurrence]
    while True:
        if recurrence != "jours_ouvres" or d.weekday() < 5:
            yield d
        d += timedelta(days=pas)


def prochaine_date(courante, recurrence, ancre=None):
    """L'occurrence qui suit « courante » (None si la tâche n'est pas récurrente)."""
    if recurrence == "aucune":
        return None
    courante = jour(courante)
    for d in suite(ancre or courante, recurrence):
        if d > courante:
            return d


def occurrences(tache, debut, fin, maximum=62):
    """Dates de la tâche entre debut et fin (inclus), à partir de sa date actuelle."""
    if not tache.get("echeance"):
        return []
    debut, fin, depuis = jour(debut), jour(fin), jour(tache["echeance"])
    # La date actuelle de la tâche compte toujours (même un samedi pour « jours ouvrés »).
    resultat = [depuis] if debut <= depuis <= fin else []
    for d in suite(tache.get("ancre") or tache["echeance"], tache.get("recurrence") or "aucune"):
        if d > fin or len(resultat) >= maximum:
            break
        if d > depuis and d >= debut:
            resultat.append(d)
    return resultat


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def _verifier_projet(projet):
    if projet == TOUS:
        raise PermissionError("La vue « tous les projets » est en lecture seule : choisis un projet.")


def valider_champs(champs, projet=None, racine=None, partiel=False):
    """Renvoie les champs nettoyés (clés de la table), ou lève TacheInvalide."""
    if not isinstance(champs, dict):
        raise TacheInvalide("Les champs d'une tâche doivent former un objet.")
    inconnus = set(champs) - set(CHAMPS)
    if inconnus:
        raise TacheInvalide("Champs inconnus : " + ", ".join(sorted(inconnus)))
    propres = {}
    if "titre" in champs or not partiel:
        titre = str(champs.get("titre") or "").strip()
        if not titre or len(titre) > 120:
            raise TacheInvalide("Le titre est obligatoire (120 caractères au plus).")
        propres["titre"] = titre
    if "date" in champs:
        d = champs["date"] or None
        if d is not None:
            try:
                d = date_.fromisoformat(str(d)).isoformat()
            except ValueError:
                raise TacheInvalide("Date attendue au format AAAA-MM-JJ.")
        propres["echeance"] = d
    if "heure" in champs:
        h = champs["heure"] or None
        if h is not None and not MOTIF_HEURE.match(str(h)):
            raise TacheInvalide("Heure attendue au format HH:MM.")
        propres["heure"] = h
    if "duree" in champs or not partiel:
        try:
            duree = int(champs.get("duree") or 30)
        except (TypeError, ValueError):
            raise TacheInvalide("Durée attendue en minutes.")
        if not 5 <= duree <= 24 * 60:
            raise TacheInvalide("Durée entre 5 minutes et 24 heures.")
        propres["duree"] = duree
    if "priorite" in champs or not partiel:
        p = champs.get("priorite") or "normale"
        if p not in PRIORITES:
            raise TacheInvalide("Priorité : " + ", ".join(PRIORITES) + ".")
        propres["priorite"] = p
    if "recurrence" in champs or not partiel:
        r = champs.get("recurrence") or "aucune"
        if r not in RECURRENCES:
            raise TacheInvalide("Récurrence : " + ", ".join(RECURRENCES) + ".")
        propres["recurrence"] = r
    if "rappel" in champs:
        r = champs["rappel"]
        if r in (None, ""):
            propres["rappel"] = None
        else:
            try:
                r = int(r)
            except (TypeError, ValueError):
                raise TacheInvalide("Rappel attendu en minutes avant le début.")
            if not 0 <= r <= 7 * 24 * 60:
                raise TacheInvalide("Rappel entre 0 minute et 7 jours avant.")
            propres["rappel"] = r
    if "note_id" in champs:
        n = champs["note_id"]
        if n in (None, ""):
            propres["note_id"] = None
        else:
            n = int(n)
            if projet and not any(x["id"] == n for x in projets.lister_notes(projet, racine)):
                raise TacheInvalide("La note liée doit appartenir au même projet.")
            propres["note_id"] = n
    if propres.get("recurrence", "aucune") != "aucune" and not propres.get("echeance") \
            and (not partiel or "echeance" in propres):
        raise TacheInvalide("Une tâche récurrente a besoin d'une date.")
    return propres


# ------------------------------------------------------------------
# Écrire (actions humaines) — chaque changement est journalisé
# ------------------------------------------------------------------

def _maintenant():
    return datetime.now().isoformat(timespec="seconds")


def _journal(conn, acteur, evenement, raison=None):
    conn.execute("INSERT INTO journal (date, acteur, evenement, raison) VALUES (?, ?, ?, ?)",
                 (_maintenant(), acteur, evenement, raison))


def _quand(t):
    return " ".join(x for x in (t.get("echeance"), t.get("heure")) if x) or "sans date"


def lire(projet, tid, racine=None):
    conn = projets._connexion(projet, racine)
    try:
        r = conn.execute("SELECT * FROM taches WHERE id = ?", (int(tid),)).fetchone()
    finally:
        conn.close()
    if r is None:
        raise KeyError(f"Aucune tâche {tid} dans le projet {projet!r}.")
    return dict(r)


def creer(projet, champs, racine=None, acteur="kayd", raison=None):
    """ACTION HUMAINE (ou proposition validée) : la tâche est enregistrée directement."""
    _verifier_projet(projet)
    t = valider_champs(champs, projet, racine)
    t.setdefault("echeance", None)
    t["ancre"] = t["echeance"] if t["recurrence"] != "aucune" else None
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO taches (titre, statut, echeance, note_id, heure, duree, priorite, "
                "recurrence, ancre, rappel, modifiee_le) VALUES (?, 'à faire', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (t["titre"], t["echeance"], t.get("note_id"), t.get("heure"), t["duree"],
                 t["priorite"], t["recurrence"], t["ancre"], t.get("rappel"), _maintenant()))
            tid = cur.lastrowid
            _journal(conn, acteur, f"tâche {tid} créée : {t['titre']} ({_quand(t)})", raison)
    finally:
        conn.close()
    return tid


def modifier(projet, tid, champs, racine=None, acteur="kayd"):
    """ACTION HUMAINE : modifier ou déplacer (date / heure) une tâche."""
    _verifier_projet(projet)
    avant = lire(projet, tid, racine)
    t = valider_champs(champs, projet, racine, partiel=True)
    if not t:
        return avant
    rec = t.get("recurrence", avant["recurrence"])
    if rec != "aucune":
        nouvelle = t.get("echeance", avant["echeance"])
        if not nouvelle:
            raise TacheInvalide("Une tâche récurrente a besoin d'une date.")
        if "echeance" in t or "recurrence" in t:
            t["ancre"] = nouvelle            # déplacer une série la ré-ancre à la nouvelle date
    else:
        t["ancre"] = None
    colonnes = ", ".join(f"{k} = ?" for k in t) + ", modifiee_le = ?"
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute(f"UPDATE taches SET {colonnes} WHERE id = ?",
                         list(t.values()) + [_maintenant(), int(tid)])
            changes = ", ".join(f"{k} {avant.get(k)!s} → {v!s}" for k, v in t.items()
                                if k != "ancre" and avant.get(k) != v)
            _journal(conn, acteur, f"tâche {tid} modifiée : {changes or 'rien'}")
    finally:
        conn.close()
    return lire(projet, tid, racine)


def supprimer(projet, tid, racine=None, acteur="kayd"):
    """ACTION HUMAINE : supprimer une tâche."""
    _verifier_projet(projet)
    t = lire(projet, tid, racine)
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute("DELETE FROM taches WHERE id = ?", (int(tid),))
            _journal(conn, acteur, f"tâche {tid} supprimée : {t['titre']}")
    finally:
        conn.close()


def terminer(projet, tid, fait, racine=None, acteur="kayd"):
    """
    ACTION HUMAINE : Fait / Pas fait.
    Tâche simple : le statut change. Tâche récurrente : l'occurrence est notée au journal et la
    tâche passe à la date suivante (elle reste « à faire »).
    Renvoie {"statut", "prochaine"}.
    """
    _verifier_projet(projet)
    t = lire(projet, tid, racine)
    statut = "fait" if fait else "pas fait"
    if t["recurrence"] == "aucune" or not t["echeance"]:
        from noyau import orchestrateur
        orchestrateur.terminer(projet, int(tid), bool(fait), racine=racine)
        return {"statut": statut, "prochaine": None}
    suivante = prochaine_date(t["echeance"], t["recurrence"], t["ancre"]).isoformat()
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute("UPDATE taches SET echeance = ?, statut = 'à faire', modifiee_le = ? WHERE id = ?",
                         (suivante, _maintenant(), int(tid)))
            _journal(conn, acteur, f"tâche {tid} : {statut} (occurrence du {t['echeance']}), "
                                   f"prochaine le {suivante}")
    finally:
        conn.close()
    return {"statut": statut, "prochaine": suivante}


def proposer(projet, champs, raison=None, racine=None, acteur="agent"):
    """JARVIS ne crée pas de tâche : il la PROPOSE. Elle passe par « À valider »."""
    _verifier_projet(projet)
    t = valider_champs(champs, projet, racine)
    propres = {k: champs[k] for k in CHAMPS if k in champs}
    contenu = (f"Tâche proposée : {t['titre']}\nQuand : {_quand(t)} · durée {t['duree']} min · "
               f"priorité {t['priorite']} · récurrence {t['recurrence']}")
    return corps_calleux.proposer(projet, "tache", contenu, titre=f"Tâche : {t['titre']}"[:80],
                                  racine=racine, acteur=acteur, raison=raison,
                                  details={"planification": propres})


# ------------------------------------------------------------------
# Lire
# ------------------------------------------------------------------

def _projets(projet, racine):
    tous = corps_calleux.lister_projets(racine)
    if projet == TOUS:
        return tous
    if projet not in tous:
        raise KeyError(f"Projet inconnu : {projet!r}")
    return [projet]


def _sortie(t, projet, d, titres_notes, occurrence):
    return {"id": t["id"], "projet": projet, "titre": t["titre"], "statut": t["statut"],
            "date": d.isoformat() if d else None, "heure": t.get("heure"), "duree": t.get("duree") or 30,
            "priorite": t.get("priorite") or "normale", "recurrence": t.get("recurrence") or "aucune",
            "rappel": t.get("rappel"), "note_id": t.get("note_id"),
            "note_titre": titres_notes.get(t.get("note_id")), "planifiee": bool(t.get("contrat")),
            "occurrence": occurrence}


def lister(projet, debut=None, jours=7, racine=None):
    """
    Les tâches d'une période : {"taches": [...], "sans_date": [...]}.
    Une tâche récurrente apparaît à chacune de ses dates (« occurrence » = date future).
    Les tâches faites restent visibles (grisées) ; celles sans date sont à part.
    """
    debut = jour(debut)
    fin = debut + timedelta(days=max(1, int(jours)) - 1)
    taches, sans_date = [], []
    for p in _projets(projet, racine):
        titres = {n["id"]: n["titre"] for n in projets.lister_notes(p, racine)}
        for t in projets.lister_taches(p, racine):
            if not t.get("echeance"):
                sans_date.append(_sortie(t, p, None, titres, False))
                continue
            for i, d in enumerate(occurrences(t, debut, fin)):
                taches.append(_sortie(t, p, d, titres, i > 0 or d > jour(t["echeance"])))
    taches.sort(key=lambda x: (x["date"], x["heure"] or "99:99", x["projet"], x["id"]))
    return {"taches": taches, "sans_date": sans_date}


def prochaines(projet=TOUS, nombre=3, racine=None, aujourd_hui=None):
    """Les prochaines tâches à faire (aujourd'hui compris), toutes dates confondues."""
    ref = jour(aujourd_hui)
    liste = [t for t in lister(projet, ref, 120, racine)["taches"] if t["statut"] != "fait"]
    vues, resultat = set(), []
    for t in liste:
        if (t["projet"], t["id"]) in vues:          # une seule fois par tâche récurrente
            continue
        vues.add((t["projet"], t["id"]))
        resultat.append(t)
        if len(resultat) >= nombre:
            break
    return resultat


def donnees(projet, debut=None, vue="semaine", racine=None, externes=None, jours=7):
    """Les données d'un hologramme « planification » (titres seulement, jamais de texte de note)."""
    debut = jour(debut)
    if vue == "semaine":
        debut = debut - timedelta(days=debut.weekday())     # du lundi au dimanche
    elif vue == "jour":
        jours = 1
    l = lister(projet, debut, jours, racine)
    notes = []
    if projet != TOUS:
        notes = [{"id": n["id"], "titre": n["titre"]} for n in projets.lister_notes(projet, racine)]
    return {
        "projet": projet, "lecture_seule": projet == TOUS, "vue": vue,
        "debut": debut.isoformat(), "jours": jours, "aujourd_hui": jour().isoformat(),
        "projets": corps_calleux.lister_projets(racine),
        "taches": l["taches"], "sans_date": l["sans_date"], "notes": notes,
        # Événements d'un calendrier extérieur (fournis par un module), en lecture seule.
        "externes": externes or {"disponible": False, "raison": "Aucun calendrier branché.", "evenements": []},
        "priorites": list(PRIORITES), "recurrences": list(RECURRENCES),
    }
