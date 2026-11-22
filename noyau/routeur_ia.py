"""
Routeur IA de JARVIS (marche 4) : la SEULE porte vers l'intelligence artificielle.

    demander_ia(tache, texte, difficulte, sensible) -> {"reponse", "fournisseur", "cout_estime"}

Règles :
1. Une demande « sensible » ne part JAMAIS vers une offre gratuite en ligne
   (les requêtes gratuites de Gemini peuvent servir à améliorer les produits
   Google). Elle va vers un modèle local (marche 9) ou, en attendant, vers
   l'IA de démonstration, qui tourne entièrement sur la machine.
2. Tâche courante non sensible : Gemini gratuit (quand il sera branché).
3. Tâche « critique » : Claude par API (quand il sera branché).
4. Compteur de coûts : tout appel qui ferait dépasser le plafond mensuel
   (BUDGET_IA_MAX_EUR_MOIS, 5 € par défaut) est BLOQUÉ.

Prototype : seul le fournisseur « demo » est réellement branché. C'est une
fausse IA, gratuite et locale, qui donne des réponses simples. Les autres
fournisseurs sont déclarés mais « non branchés » : le routeur les ignore
tant que leur code et leur clé ne sont pas en place.
"""

import re
from collections import Counter

from noyau import reglages, systeme
from noyau.outils import jour, mots_cles

DIFFICULTES = ("courante", "difficile", "critique")


class BudgetDepasse(Exception):
    """Levée quand un appel ferait dépasser le plafond mensuel."""


# ------------------------------------------------------------------
# Fournisseurs
# ------------------------------------------------------------------

class Fournisseur:
    nom = "?"
    gratuit = False         # offre gratuite = peut réutiliser les données
    local = False           # tourne sur la machine (rien ne sort)
    branche = False         # code d'appel réellement écrit
    cle_reglage = None      # nom de la clé dans reglages.local

    def disponible(self):
        if not self.branche:
            return False
        return not self.cle_reglage or bool(reglages.lire(self.cle_reglage))

    def estimer_cout(self, texte):
        return 0.0

    def repondre(self, tache, texte, temperature=None):
        raise NotImplementedError


class IADemo(Fournisseur):
    """Fausse IA locale et gratuite, pour faire tourner le prototype sans clé."""
    nom = "demo"
    local = True
    branche = True

    def __init__(self, cout_par_appel=0.0):
        self.cout_par_appel = cout_par_appel  # permet de simuler un coût en test

    def estimer_cout(self, texte):
        return self.cout_par_appel

    def repondre(self, tache, texte, temperature=None):
        from noyau import ia_demo
        if tache in ia_demo.TACHES:
            return ia_demo.repondre(tache, texte, temperature)
        if tache == "planifier":
            sujet = texte.strip().splitlines()[0] if texte.strip() else "la tâche"
            return ("1. Préparer : rassembler ce qu'il faut pour « {0} » (10 min)\n"
                    "2. Faire : {0} (25 min)\n"
                    "3. Vérifier le résultat et le noter (5 min)").format(sujet)
        if tache in ("synthetiser", "comparer"):
            frequents = [m for m, _ in Counter(mots_cles(texte)).most_common(5)]
            if tache == "comparer":
                return "Points communs : " + (", ".join(frequents) or "aucun mot commun net")
            return ("Ces notes tournent autour de : " + (", ".join(frequents) or "thèmes variés")
                    + ". Elles sont souvent utilisées ensemble : les regrouper dans une "
                      "synthèse aide à retrouver l'idée d'ensemble.")
        return "(Réponse de démonstration) J'ai bien reçu : " + texte.strip()[:200]


class GeminiGratuit(Fournisseur):
    nom = "gemini"
    gratuit = True
    cle_reglage = "CLE_API_GEMINI"
    branche = False  # à brancher plus tard (avec la clé de Kayd)


class ClaudeAPI(Fournisseur):
    nom = "claude"
    cle_reglage = "CLE_API_ANTHROPIC"
    branche = False  # à brancher plus tard

    def estimer_cout(self, texte):
        jetons = len(texte) / 4 + 800       # texte envoyé + réponse moyenne
        return round(jetons / 1_000_000 * 15, 4)  # estimation prudente en €


class ModeleLocal(Fournisseur):
    nom = "local"
    local = True
    branche = False  # marche 9 (Ollama)


def fournisseurs_par_defaut():
    return {f.nom: f for f in (IADemo(), GeminiGratuit(), ClaudeAPI(), ModeleLocal())}


# ------------------------------------------------------------------
# Choix du fournisseur
# ------------------------------------------------------------------

def choisir(difficulte, sensible, fournisseurs):
    def ok(nom):
        f = fournisseurs.get(nom)
        return f is not None and f.disponible()

    if sensible:
        ordre = ["local", "demo"]           # jamais une offre gratuite en ligne
    elif difficulte == "critique":
        ordre = ["claude", "gemini", "local", "demo"]
    else:
        ordre = ["gemini", "local", "demo"]
    for nom in ordre:
        if ok(nom):
            f = fournisseurs[nom]
            if sensible and f.gratuit and not f.local:
                continue  # double sécurité
            return f
    raise RuntimeError("Aucune IA disponible pour cette demande.")


# ------------------------------------------------------------------
# Budget
# ------------------------------------------------------------------

def plafond_mensuel():
    try:
        return float(reglages.lire("BUDGET_IA_MAX_EUR_MOIS").replace(",", "."))
    except ValueError:
        return 5.0


def depense_du_mois(date=None, racine=None):
    mois = jour(date).strftime("%Y-%m")
    conn = systeme.connexion(racine)
    try:
        r = conn.execute("SELECT montant_estime FROM budget_ia WHERE mois = ?", (mois,)).fetchone()
        return r["montant_estime"] if r else 0.0
    finally:
        conn.close()


def _noter_appel(conn, date, f, tache, difficulte, sensible, cout, statut):
    conn.execute(
        "INSERT INTO appels_ia (date, fournisseur, tache, difficulte, sensible, cout_estime, statut) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (jour(date).isoformat(), f.nom, tache, difficulte, int(bool(sensible)), cout, statut))


# ------------------------------------------------------------------
# La porte unique
# ------------------------------------------------------------------

def estimer(texte="", difficulte="courante", sensible=False, fournisseurs=None):
    """Sans rien appeler : quelle IA serait choisie, et combien coûterait l'appel."""
    f = choisir(difficulte, sensible, fournisseurs or fournisseurs_par_defaut())
    return f, f.estimer_cout(texte)


def demander_ia(tache, texte="", difficulte="courante", sensible=False, date=None,
                racine=None, fournisseurs=None, plafond=None, temperature=None):
    """
    temperature : de 0 (réponses sages et constantes) à 1 et plus (réponses
    créatives et variées). None = valeur par défaut du fournisseur.
    """
    if difficulte not in DIFFICULTES:
        raise ValueError(f"Difficulté inconnue : {difficulte!r} ({', '.join(DIFFICULTES)}).")
    fournisseurs = fournisseurs or fournisseurs_par_defaut()
    plafond = plafond_mensuel() if plafond is None else plafond
    f = choisir(difficulte, sensible, fournisseurs)
    cout = f.estimer_cout(texte)
    mois = jour(date).strftime("%Y-%m")

    conn = systeme.connexion(racine)
    try:
        with conn:
            deja = conn.execute("SELECT montant_estime FROM budget_ia WHERE mois = ?",
                                (mois,)).fetchone()
            deja = deja["montant_estime"] if deja else 0.0
            if cout > 0 and deja + cout > plafond:
                _noter_appel(conn, date, f, tache, difficulte, sensible, cout, "bloqué (budget)")
                raise BudgetDepasse(
                    f"Plafond IA atteint : {deja:.2f} € déjà dépensés ce mois-ci, "
                    f"cet appel coûterait {cout:.2f} €, plafond {plafond:.2f} €.")
    finally:
        conn.close()

    if temperature is None:
        reponse = f.repondre(tache, texte)
    else:
        reponse = f.repondre(tache, texte, temperature=temperature)

    conn = systeme.connexion(racine)
    try:
        with conn:
            conn.execute(
                "INSERT INTO budget_ia (mois, montant_estime) VALUES (?, ?) "
                "ON CONFLICT(mois) DO UPDATE SET montant_estime = montant_estime + excluded.montant_estime",
                (mois, cout))
            _noter_appel(conn, date, f, tache, difficulte, sensible, cout, "ok")
    finally:
        conn.close()
    return {"reponse": reponse, "fournisseur": f.nom, "cout_estime": cout}


def nombre_appels(racine=None):
    conn = systeme.connexion(racine)
    try:
        return conn.execute("SELECT COUNT(*) FROM appels_ia WHERE statut = 'ok'").fetchone()[0]
    finally:
        conn.close()


def etapes_depuis_texte(texte):
    """Lit des lignes « 1. Faire ceci (10 min) » et renvoie [{etape, duree_min}]."""
    etapes = []
    for ligne in texte.splitlines():
        m = re.match(r"\s*\d+[.)]\s*(.+?)\s*\((\d+)\s*min\)\s*$", ligne)
        if m:
            etapes.append({"etape": m.group(1), "duree_min": int(m.group(2))})
    return etapes
