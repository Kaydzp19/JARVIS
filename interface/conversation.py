"""
La conversation de l'interface, en mode RÉEL (données de ~/.jarvis).

Le routeur décide par CODE (mots-clés), sans appeler d'IA :
- « machine », « CPU », « batterie »…   -> hologramme machine
- « météo », « pluie »…                 -> hologramme météo (si la position est réglée)
- « nuit », « sommeil »…                -> résumé de la nuit
- « dépenses », « budget », « coût »…   -> graphique des dépenses IA
- « ouvre la note X »                   -> l'éditeur local (ou refus si la note est sensible)
- tout le reste                         -> se_souvenir : la vague sur la sphère + notes retenues

La réponse contient la ligne d'outil telle qu'elle a été appelée
(ex. se_souvenir(projet="A", requête="…")) et « routeur : aucun appel IA ».
Les notes ayant servi ensemble sont renforcées par activer (notes validées
seulement, jamais dans la vue « tous les projets », qui est en lecture seule).
"""

import re
from datetime import date, timedelta

from noyau import affichage
from noyau import corps_calleux as cc
from noyau import projets, systeme
from noyau.outils import normaliser

from interface import fournisseurs

TOUS = affichage.PROJET_TRANSVERSAL
PAR_PROJET, PAR_PROJET_TOUS = 6, 4
ROUTEUR_SANS_IA = "routeur : aucun appel IA"

ROUTES = [
    ("machine", re.compile(r"\b(machine|ordinateur|ordi|cpu|processeur|ram|memoire vive|disque|"
                           r"batterie|processus)\b")),
    ("meteo", re.compile(r"\b(meteo|pluie|pleuvoir|soleil|temps qu.il fait|temperature dehors)\b")),
    ("resume_nuit", re.compile(r"\b(nuit|dormi|sommeil|reveil)\b")),
    ("graphique", re.compile(r"\b(depenses?|budget|couts?|coute|facture|plafond)\b")),
]
MOTIF_OUVRIR = re.compile(r"^(?:ouvre|ouvrir|montre|affiche)(?:[- ]moi)? la note (.+?)\s*[?.!]*$", re.I)


MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def _guillemets(texte):
    return texte.replace('"', "'")


def _fr(x, decimales=1):
    """Nombre au format français (virgule), ou « — » si inconnu."""
    return "—" if x is None else f"{x:.{decimales}f}".replace(".", ",")


def router(texte):
    """Renvoie le nom de la route choisie pour ce texte (par code, sans IA)."""
    if MOTIF_OUVRIR.match(texte.strip()):
        return "ouvrir_note"
    n = normaliser(texte)
    for nom, motif in ROUTES:
        if motif.search(n):
            return nom
    return "se_souvenir"


# ------------------------------------------------------------------
# Données des scènes (aussi utilisées pour les mises à jour)
# ------------------------------------------------------------------

def _depenses_par_jour(jours, racine=None, aujourd_hui=None):
    aujourd_hui = aujourd_hui or date.today()
    debut = aujourd_hui - timedelta(days=jours - 1)
    conn = systeme.connexion(racine)
    try:
        sommes = {r[0]: r[1] for r in conn.execute(
            "SELECT date, SUM(cout_estime) FROM appels_ia WHERE date >= ? GROUP BY date",
            (debut.isoformat(),))}
    finally:
        conn.close()
    return [{"etiquette": (debut + timedelta(days=i)).strftime("%d/%m"),
             "valeur": round(sommes.get((debut + timedelta(days=i)).isoformat(), 0.0), 3)}
            for i in range(jours)]


def donnees_depenses(periode="6 mois", racine=None):
    d = fournisseurs.depenses(racine, mois=12 if periode == "12 mois" else 6)
    if periode in ("7 j", "30 j", "24 h"):
        serie = _depenses_par_jour(1 if periode == "24 h" else int(periode.split()[0]), racine)
    else:
        serie = [{"etiquette": MOIS[int(m["mois"][5:7]) - 1], "valeur": m["montant"]} for m in d["serie"]]
    return {"source": "depenses_ia", "type": "barres", "unite": "€", "periode": periode,
            "serie": serie, "plafond": d["plafond"], "mois": d["mois"],
            "aujourd_hui": d["aujourd_hui"], "session": d["session"]}


def rafraichir(ev, action, params, racine=None):
    """Nouvelles données pour une action de lecture venue d'un widget (ou None)."""
    scene, d = ev["scene"], ev["donnees"]
    if scene == "machine":
        return fournisseurs.machine()
    if scene == "meteo":
        return fournisseurs.meteo()
    if scene == "resume_nuit" and ev.get("projet") not in (None, TOUS):
        return fournisseurs.nuit(ev["projet"], racine)
    if scene == "graphique" and d.get("source") == "depenses_ia":
        periode = params.get("periode") or d.get("periode") or "6 mois"
        if periode not in affichage.PERIODES:
            raise ValueError("Période inconnue.")
        return donnees_depenses(periode, racine)
    return None


# ------------------------------------------------------------------
# Répondre
# ------------------------------------------------------------------

def _projets_cibles(projet, racine):
    tous = cc.lister_projets(racine)
    if projet == TOUS:
        return tous
    if projet not in tous:
        raise KeyError(f"Projet inconnu : {projet!r}")
    return [projet]


def _projet_par_defaut(projet, racine):
    if projet and projet != TOUS:
        return projet
    tous = cc.lister_projets(racine)
    return tous[0] if tous else None


def _liste_titres(retenues):
    return ", ".join(f"« {r['titre']} »" for r in retenues)


def _se_souvenir(texte, projet, racine):
    cibles = _projets_cibles(projet, racine)
    limite = PAR_PROJET_TOUS if projet == TOUS else PAR_PROJET
    traces = [cc.se_souvenir_trace(p, texte, limite, racine) for p in cibles]
    outil = f'se_souvenir(projet="{_guillemets(projet)}", requête="{_guillemets(texte)}")'
    retenues = [dict(r, projet=t["projet"]) for t in traces for r in t["retenues"]]
    if not retenues:
        reponse = "Je n'ai trouvé aucune note pour répondre."
    elif projet == TOUS:
        reponse = (f"{len(retenues)} notes retenues dans {len(traces)} projets (vue en lecture "
                   f"seule) : {_liste_titres(retenues[:6])}" + ("…" if len(retenues) > 6 else "."))
    else:
        reponse = (f"J'ai retenu {len(retenues)} note(s) dans « {projet} » : "
                   f"{_liste_titres(retenues)}. Calcul par code (pertinence, force des synapses, "
                   f"fraîcheur, importance).")
    renforcement = None
    if projet != TOUS and retenues:
        cc.journal(projet, f"conversation · {outil}", ROUTEUR_SANS_IA, racine=racine,
                   acteur="jarvis (conversation)")
        renforcement = cc.activer(projet, [r["id"] for r in retenues], racine=racine,
                                  acteur="jarvis (conversation)",
                                  raison="notes servies ensemble pour répondre")
    ev = None
    if retenues:
        ev = affichage.afficher(
            "notes_retenues", "Notes retenues",
            {"requete": texte, "notes": [{"id": r["id"], "titre": r["titre"], "projet": r["projet"],
                                          "score": r["score"], "rang": r["rang"],
                                          "sensible": r["sensible"]} for r in retenues]},
            projet=projet, controles={"tri": ["rang", "score", "titre"]},
            actions=[{"id": "ouvrir_note", "libelle": "Ouvrir la note"}] + (
                [] if projet == TOUS else
                [{"id": "creer_synthese", "libelle": "Proposer une synthèse", "type": "ecriture"}]),
            racine=racine)
    return {"route": "se_souvenir", "outil": outil, "routeur": ROUTEUR_SANS_IA,
            "reponse": reponse, "affichage": ev, "renforcement": renforcement,
            "recherche": {"projet": projet, "traces": traces}}


def _ouvrir_note(texte, projet, racine):
    titre = MOTIF_OUVRIR.match(texte.strip()).group(1).strip(" «»\"'")
    p = _projet_par_defaut(projet, racine)
    outil = f'ouvrir_note(projet="{_guillemets(p or "")}", titre="{_guillemets(titre)}")'
    note = None
    if p:
        note = next((n for n in projets.lister_notes(p, racine)
                     if normaliser(n["titre"]) == normaliser(titre)), None)
    base = {"route": "ouvrir_note", "outil": outil, "routeur": ROUTEUR_SANS_IA, "recherche": None}
    if note is None:
        return dict(base, reponse=f"Je ne trouve pas la note « {titre} » dans le projet {p}.",
                    affichage=None)
    if note["sensible"]:
        taille = len(projets.lire_note(p, note["id"], racine))
        ev = affichage.afficher("note_privee", "Note sensible", {
            "titre": note["titre"], "id": note["id"], "caracteres": taille},
            projet=p, racine=racine)
        return dict(base, affichage=ev,
                    reponse=f"« {note['titre']} » est une note sensible : je ne l'affiche pas. "
                            "Tu peux l'ouvrir toi-même dans l'éditeur local.")
    return dict(base, affichage=None, ouvrir_note={"projet": p, "id": note["id"]},
                reponse=f"J'ouvre « {note['titre']} » dans l'éditeur local.")


def _hologramme(route, projet, racine):
    p = _projet_par_defaut(projet, racine)
    if route == "machine":
        ev = affichage.afficher("machine", "Machine", fournisseurs.machine(), racine=racine,
                                actions=[{"id": "rafraichir", "libelle": "Actualiser"}])
        d = ev["donnees"]
        reponse = (f"Processeur {_fr(d['cpu'], 0)} %, mémoire {_fr((d['ram'] or {}).get('pourcent'), 0)} %, "
                   f"disque {_fr((d['disque'] or {}).get('pourcent'), 0)} %. "
                   "Température du processeur : indisponible sans droits administrateur.")
        outil = "machine()"
    elif route == "meteo":
        d = fournisseurs.meteo()
        ev = affichage.afficher("meteo", "Météo", d, racine=racine,
                                actions=[{"id": "rafraichir", "libelle": "Actualiser"}])
        reponse = (f"Il fait {_fr(d['actuelle']['temperature'], 0)} °C." if d["disponible"]
                   else d["raison"])
        outil = "meteo()"
    elif route == "resume_nuit":
        if p is None:
            return None
        d = fournisseurs.nuit(p, racine)
        ev = affichage.afficher("resume_nuit", f"Résumé de la nuit · {p}", d, projet=p,
                                racine=racine)
        reponse = (f"Dernière nuit de « {p} » : {d['renforcees']} synapse(s) renforcée(s), "
                   f"{d['archivees']} archivée(s), {d['propositions_en_attente']} proposition(s) "
                   "en attente de ta validation."
                   if d["date"] else f"« {p} » n'a pas encore dormi.")
        outil = f'resume_nuit(projet="{_guillemets(p)}")'
    else:  # graphique des dépenses
        d = donnees_depenses("6 mois", racine)
        ev = affichage.afficher("graphique", "Dépenses IA", d, racine=racine,
                                controles={"periode": ["7 j", "30 j", "6 mois", "12 mois"]})
        reponse = f"Ce mois-ci : {_fr(d['mois'], 2)} € sur un plafond de {_fr(d['plafond'], 2)} €."
        outil = 'depenses_ia(periode="6 mois")'
    return {"route": route, "outil": outil, "routeur": ROUTEUR_SANS_IA, "reponse": reponse,
            "affichage": ev, "recherche": None}


def repondre(texte, projet, racine=None):
    """Point d'entrée : une phrase de Kayd -> réponse, trace éventuelle, hologramme éventuel."""
    texte = (texte or "").strip()
    if not texte:
        raise ValueError("Message vide.")
    if len(texte) > 500:
        raise ValueError("Message trop long (500 caractères au plus).")
    route = router(texte)
    if route == "ouvrir_note":
        return _ouvrir_note(texte, projet, racine)
    if route != "se_souvenir":
        r = _hologramme(route, projet, racine)
        if r is not None:
            return r
    if not cc.lister_projets(racine):
        return {"route": "aucun_projet", "outil": None, "routeur": ROUTEUR_SANS_IA,
                "reponse": "Aucun projet pour l'instant. Lance « python3 jarvis.py demo » "
                           "pour créer les projets de démonstration.",
                "affichage": None, "recherche": None}
    return _se_souvenir(texte, projet or _projet_par_defaut(None, racine), racine)
