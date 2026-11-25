"""
Affichages à la demande (les « hologrammes ») : le contrat entre JARVIS et l'interface.

JARVIS ne dessine rien. Il ÉCRIT un événement d'affichage (une scène + des
données), qui est rangé et journalisé ; l'interface le lit et construit le
widget. L'interface ne décide rien : elle affiche.

    afficher(scene, titre, donnees, projet=None, controles=None, actions=None)
        -> crée un événement (validé par le schéma), renvoie l'événement
    mettre_a_jour(id, donnees)
        -> même événement, nouvelles données (version + 1) : le widget se met à jour sur place
    recevoir_action(id, action, params, rafraichir=None)
        -> une action venue d'un widget, journalisée. Deux cas :
           - lecture (changer de période, recharger…) : « rafraichir » fournit les
             nouvelles données, puis mettre_a_jour ;
           - écriture (écrire, supprimer, publier, payer…) : JAMAIS exécutée.
             Elle devient une proposition « à valider » (garde d'écriture).
    lister(apres=0), lire(id), valider(evenement)

Règles du contrat (vérifiées par valider) :
- une scène est un identifiant simple ; une scène inconnue de l'interface est
  affichée par un widget générique (tableau ou graphique simple), jamais en erreur ;
- un widget ne montre qu'UN projet (sauf la vue transversale en lecture seule) ;
- aucun texte de note : les clés « contenu », « texte », « extrait » sont refusées.

Ce module est générique : il ne connaît aucune scène en particulier.
Rangement : ~/.jarvis/systeme.db (tables affichages et affichages_actions).
"""

import json
import re
from datetime import datetime

from noyau import systeme

SCHEMA = """
CREATE TABLE IF NOT EXISTS affichages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    cree_le   TEXT NOT NULL,
    maj_le    TEXT NOT NULL,
    version   INTEGER NOT NULL DEFAULT 1,
    scene     TEXT NOT NULL,
    projet    TEXT,
    evenement TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS affichages_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    affichage   INTEGER NOT NULL,
    action      TEXT NOT NULL,
    params      TEXT NOT NULL,
    resultat    TEXT NOT NULL
);
"""

MOTIF_SCENE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MOTIF_ACTION = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
CLES_INTERDITES = {"contenu", "texte", "extrait", "corps"}      # le texte des notes ne sort jamais
CONTROLES = {"onglets", "filtres", "tri", "periode"}
PERIODES = ("24 h", "7 j", "30 j", "6 mois", "12 mois")
TYPES_ACTION = ("lecture", "ecriture")
# Mots qui désignent une action d'écriture, même si l'action est déclarée « lecture ».
VERBES_ECRITURE = ("ecrire", "creer", "modifier", "supprimer", "effacer", "publier", "payer",
                   "acheter", "envoyer", "valider", "refuser", "archiver")
TAILLE_MAX = 64_000
PROJET_TRANSVERSAL = "*"   # vue « tous les projets » : lecture seule


class AffichageInvalide(ValueError):
    """L'événement ne respecte pas le contrat d'affichage."""


def _maintenant(date=None):
    return (date or datetime.now()).isoformat(timespec="seconds")


def _connexion(racine=None):
    conn = systeme.connexion(racine)
    conn.executescript(SCHEMA)
    return conn


# ------------------------------------------------------------------
# Le schéma
# ------------------------------------------------------------------

def _cles_interdites(valeur, chemin="donnees"):
    """Renvoie les chemins des clés interdites trouvées (recherche en profondeur)."""
    trouvees = []
    if isinstance(valeur, dict):
        for k, v in valeur.items():
            if str(k).lower() in CLES_INTERDITES:
                trouvees.append(f"{chemin}.{k}")
            trouvees += _cles_interdites(v, f"{chemin}.{k}")
    elif isinstance(valeur, list):
        for i, v in enumerate(valeur):
            trouvees += _cles_interdites(v, f"{chemin}[{i}]")
    return trouvees


def est_ecriture(action):
    """Vrai si l'action écrit, supprime, publie ou paie (d'après son type OU son nom)."""
    nom = action.get("id", "") if isinstance(action, dict) else str(action)
    if isinstance(action, dict) and action.get("type") == "ecriture":
        return True
    return any(nom == v or nom.startswith(v + "_") for v in VERBES_ECRITURE)


def valider(ev):
    """
    Vérifie un événement d'affichage. Renvoie la liste des erreurs (vide si tout va bien).
    Forme : {scene, titre, donnees, projet?, controles?, actions?}
    """
    erreurs = []
    if not isinstance(ev, dict):
        return ["l'événement doit être un objet"]
    inconnues = set(ev) - {"scene", "titre", "donnees", "projet", "controles", "actions",
                           "id", "version", "cree_le", "maj_le", "fermeture"}
    if inconnues:
        erreurs.append(f"champs inconnus : {', '.join(sorted(inconnues))}")
    scene = ev.get("scene")
    if not isinstance(scene, str) or not MOTIF_SCENE.match(scene):
        erreurs.append("scene : identifiant attendu (minuscules, chiffres, _)")
    titre = ev.get("titre")
    if not isinstance(titre, str) or not titre.strip() or len(titre) > 120:
        erreurs.append("titre : texte de 1 à 120 caractères")
    donnees = ev.get("donnees")
    if not isinstance(donnees, dict):
        erreurs.append("donnees : objet attendu")
    else:
        for chemin in _cles_interdites(donnees):
            erreurs.append(f"{chemin} : le texte des notes n'est jamais envoyé à l'interface")
        if len(json.dumps(donnees, ensure_ascii=False)) > TAILLE_MAX:
            erreurs.append("donnees : trop volumineuses")
    projet = ev.get("projet")
    if projet is not None and (not isinstance(projet, str) or not projet.strip()):
        erreurs.append("projet : nom de projet ou absent")
    if "fermeture" in ev and not (isinstance(ev["fermeture"], (int, float))
                                  and 0 <= ev["fermeture"] <= 600):
        erreurs.append("fermeture : nombre de secondes entre 0 et 600 (0 = reste ouvert)")
    controles = ev.get("controles") or {}
    if not isinstance(controles, dict):
        erreurs.append("controles : objet attendu")
    else:
        for k, v in controles.items():
            if k not in CONTROLES:
                erreurs.append(f"controles.{k} : contrôle inconnu ({', '.join(sorted(CONTROLES))})")
            elif not (isinstance(v, list) and v and all(isinstance(x, str) and x for x in v)):
                erreurs.append(f"controles.{k} : liste de textes attendue")
            elif k == "periode" and any(x not in PERIODES for x in v):
                erreurs.append(f"controles.periode : valeurs permises {', '.join(PERIODES)}")
    actions = ev.get("actions") or []
    if not isinstance(actions, list):
        erreurs.append("actions : liste attendue")
    else:
        vus = set()
        for i, a in enumerate(actions):
            if not isinstance(a, dict) or not MOTIF_ACTION.match(str(a.get("id", ""))):
                erreurs.append(f"actions[{i}] : id attendu (minuscules, chiffres, _)")
                continue
            if a["id"] in vus:
                erreurs.append(f"actions[{i}] : id en double")
            vus.add(a["id"])
            if not isinstance(a.get("libelle"), str) or not a["libelle"].strip():
                erreurs.append(f"actions[{i}] : libelle attendu")
            if a.get("type", "lecture") not in TYPES_ACTION:
                erreurs.append(f"actions[{i}] : type lecture ou ecriture")
            if projet == PROJET_TRANSVERSAL and est_ecriture(a):
                erreurs.append(f"actions[{i}] : la vue « tous les projets » est en lecture seule")
    return erreurs


def _normaliser(ev):
    """Ajoute les valeurs par défaut (type des actions, contrôles vides)."""
    ev = dict(ev)
    ev["titre"] = ev["titre"].strip()
    ev.setdefault("projet", None)
    ev["controles"] = dict(ev.get("controles") or {})
    ev["actions"] = [dict(a, type="ecriture" if est_ecriture(a) else a.get("type", "lecture"))
                     for a in (ev.get("actions") or [])]
    return ev


# ------------------------------------------------------------------
# Écrire et lire les événements
# ------------------------------------------------------------------

def _journaliser(projet, evenement, raison, racine):
    """Ajoute une ligne au journal du projet concerné (s'il y en a un)."""
    if not projet or projet == PROJET_TRANSVERSAL:
        return
    from noyau import corps_calleux as cc
    if projet in cc.lister_projets(racine):
        cc.journal(projet, evenement, raison, racine=racine, acteur="jarvis (affichage)")


def _depuis_ligne(r):
    ev = json.loads(r["evenement"])
    ev.update(id=r["id"], version=r["version"], cree_le=r["cree_le"], maj_le=r["maj_le"])
    return ev


def afficher(scene, titre, donnees, projet=None, controles=None, actions=None,
             fermeture=None, racine=None, date=None):
    """Crée un événement d'affichage. Lève AffichageInvalide si le contrat n'est pas respecté."""
    ev = {"scene": scene, "titre": titre, "donnees": donnees, "projet": projet,
          "controles": controles or {}, "actions": actions or []}
    if fermeture is not None:
        ev["fermeture"] = fermeture
    erreurs = valider(ev)
    if erreurs:
        raise AffichageInvalide("; ".join(erreurs))
    ev = _normaliser(ev)
    quand = _maintenant(date)
    conn = _connexion(racine)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO affichages (cree_le, maj_le, scene, projet, evenement) "
                "VALUES (?, ?, ?, ?, ?)",
                (quand, quand, scene, projet, json.dumps(ev, ensure_ascii=False)))
            aid = cur.lastrowid
    finally:
        conn.close()
    _journaliser(projet, f"affichage {aid} : {scene} « {ev['titre']} »", "demande d'affichage",
                 racine)
    return lire(aid, racine)


def lire(aid, racine=None):
    conn = _connexion(racine)
    try:
        r = conn.execute("SELECT * FROM affichages WHERE id = ?", (int(aid),)).fetchone()
    finally:
        conn.close()
    if r is None:
        raise KeyError(f"Aucun affichage {aid}.")
    return _depuis_ligne(r)


def lister(apres=0, limite=50, racine=None):
    """Les événements créés ou mis à jour (les plus récents en dernier)."""
    conn = _connexion(racine)
    try:
        lignes = conn.execute("SELECT * FROM affichages WHERE id > ? ORDER BY id DESC LIMIT ?",
                              (int(apres), int(limite))).fetchall()
    finally:
        conn.close()
    return [_depuis_ligne(r) for r in reversed(lignes)]


def mettre_a_jour(aid, donnees, titre=None, racine=None, date=None):
    """Remplace les données d'un événement (même id, version + 1)."""
    ev = lire(aid, racine)
    for k in ("id", "version", "cree_le", "maj_le"):
        ev.pop(k)
    ev["donnees"] = donnees
    if titre:
        ev["titre"] = titre
    erreurs = valider(ev)
    if erreurs:
        raise AffichageInvalide("; ".join(erreurs))
    conn = _connexion(racine)
    try:
        with conn:
            conn.execute("UPDATE affichages SET evenement = ?, maj_le = ?, version = version + 1 "
                         "WHERE id = ?",
                         (json.dumps(_normaliser(ev), ensure_ascii=False), _maintenant(date),
                          int(aid)))
    finally:
        conn.close()
    return lire(aid, racine)


def _noter_action(aid, action, params, resultat, racine, date):
    conn = _connexion(racine)
    try:
        with conn:
            conn.execute("INSERT INTO affichages_actions (date, affichage, action, params, resultat) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (_maintenant(date), int(aid), action,
                          json.dumps(params, ensure_ascii=False), resultat))
    finally:
        conn.close()


def actions_recues(aid=None, racine=None):
    conn = _connexion(racine)
    try:
        if aid is None:
            lignes = conn.execute("SELECT * FROM affichages_actions ORDER BY id").fetchall()
        else:
            lignes = conn.execute("SELECT * FROM affichages_actions WHERE affichage = ? ORDER BY id",
                                  (int(aid),)).fetchall()
    finally:
        conn.close()
    return [dict(r, params=json.loads(r["params"])) for r in lignes]


def recevoir_action(aid, action, params=None, rafraichir=None, racine=None, date=None):
    """
    Une action envoyée par un widget : affichage.action({widget, action, params}).
    Renvoie {"type": "mise_a_jour", "affichage": ev}
         ou {"type": "a_valider", "proposition": id, "projet": p}
         ou {"type": "inchange", "affichage": ev, "raison": …}.
    « rafraichir(evenement, action, params) » fournit les nouvelles données (lecture).
    Une action d'écriture n'est JAMAIS exécutée : elle devient une proposition à valider.
    """
    params = params if isinstance(params, dict) else {}
    if not MOTIF_ACTION.match(str(action or "")):
        raise AffichageInvalide("action : identifiant attendu")
    ev = lire(aid, racine)
    declaree = next((a for a in ev["actions"] if a["id"] == action), None)
    controle = action in ("periode", "onglet", "filtre", "tri", "rafraichir")
    if declaree is None and not controle:
        raise AffichageInvalide(f"action « {action} » non déclarée par ce widget")
    projet = ev.get("projet")

    if est_ecriture(declaree or action):
        if not projet or projet == PROJET_TRANSVERSAL:
            _noter_action(aid, action, params, "refusée (aucun projet)", racine, date)
            raise PermissionError("Action d'écriture hors projet : refusée (vue en lecture seule).")
        from noyau import corps_calleux as cc
        libelle = (declaree or {}).get("libelle", action)
        detail = json.dumps(params, ensure_ascii=False) if params else "aucun paramètre"
        pid = cc.proposer(projet, "tache",
                          f"Action demandée depuis le widget « {ev['titre']} » : {libelle}.\n"
                          f"Paramètres : {detail}\n"
                          "Rien n'a été exécuté : à valider par Kayd.",
                          titre=f"À valider : {libelle}"[:80], racine=racine,
                          acteur="interface (widget)",
                          raison="action d'écriture demandée depuis un hologramme")
        _noter_action(aid, action, params, f"proposition {pid} à valider", racine, date)
        return {"type": "a_valider", "proposition": pid, "projet": projet}

    nouvelles = rafraichir(ev, action, params) if rafraichir else None
    if nouvelles is None:
        _noter_action(aid, action, params, "inchangé", racine, date)
        _journaliser(projet, f"affichage {aid} : action {action}", "lecture, rien à changer", racine)
        return {"type": "inchange", "affichage": ev, "raison": "aucune donnée nouvelle"}
    maj = mettre_a_jour(aid, nouvelles, racine=racine, date=date)
    _noter_action(aid, action, params, f"mis à jour (version {maj['version']})", racine, date)
    _journaliser(projet, f"affichage {aid} : action {action} → mise à jour", "lecture", racine)
    return {"type": "mise_a_jour", "affichage": maj}
