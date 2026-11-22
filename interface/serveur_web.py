"""
Cockpit web de JARVIS (marche 7) : un petit site qui tourne sur ta machine.

    python3 jarvis.py cockpit

- Il n'écoute que l'adresse 127.0.0.1 : seul ton ordinateur peut l'ouvrir.
- Accès protégé par un jeton (une sorte de mot de passe) : soit
  COCKPIT_JETON dans reglages.local, soit un jeton tiré au hasard à chaque
  lancement et affiché dans le terminal.
- L'interface lit l'état et le journal ; les décisions restent humaines
  (valider / refuser une proposition, Fait / Pas fait, écrire une note).

Uniquement la bibliothèque standard de Python.
"""

import hmac
import json
import secrets
import sys
import webbrowser
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RACINE_DEPOT = Path(__file__).resolve().parent.parent
if str(RACINE_DEPOT) not in sys.path:
    sys.path.insert(0, str(RACINE_DEPOT))

from noyau import agent as agents_mod  # noqa: E402
from noyau import corps_calleux as cc  # noqa: E402
from noyau import modules, orchestrateur, projets, reglages, routeur_ia, synapses  # noqa: E402

PAGE = Path(__file__).resolve().parent / "cockpit.html"
NOM_COOKIE = "jarvis_jeton"


# ------------------------------------------------------------------
# Données envoyées à la page
# ------------------------------------------------------------------

def etat(racine=None, projet=None):
    """
    L'état du cockpit. Avec « projet », les listes ne montrent QUE ce projet
    (un projet à la fois) ; la liste des projets (onglets) reste complète.
    """
    noms = cc.lister_projets(racine)
    lignes_journal, propositions, projets_info, taches = [], [], [], []
    compte_agents = {}
    for p in noms:
        e = cc.etat_projet(p, racine)
        projets_info.append({"nom": p, "sensible": e["sensible"],
                             "demo": cc.projet_demo(p, racine),
                             "notes": len(projets.lister_notes(p, racine)),
                             "taches_a_faire": sum(t["statut"] in orchestrateur.STATUTS_A_FAIRE
                                                   for t in e["taches"])})
        if projet is not None and p != projet:
            continue
        for t in e["taches"]:
            taches.append({"projet": p, "id": t["id"], "titre": t["titre"], "statut": t["statut"],
                           "echeance": t["echeance"], "planifiee": bool(t["contrat"])})
        for prop in e["propositions_en_attente"]:
            propositions.append(dict(prop, projet=p))
        for l in projets.lire_journal(p, racine):
            lignes_journal.append(dict(l, projet=p))
            if l["acteur"].startswith("agent:"):
                nom = l["acteur"][6:]
                compte_agents[nom] = compte_agents.get(nom, 0) + 1
    lignes_journal.sort(key=lambda l: l["date"], reverse=True)
    agents = [dict(a.decrire(), actions=compte_agents.get(n, 0))
              for n, a in agents_mod.charger_tous(racine=racine).items()]
    if projet is None:
        maintenant = orchestrateur.prochaine_action(racine)
    else:
        maintenant = next((t["contrat"] for t in orchestrateur.taches_a_faire(racine)
                           if t["projet"] == projet and t["contrat"]), None)
    return {
        "projet": projet,
        "mode_ia": routeur_ia.mode_ia(),
        "maintenant": maintenant,
        "taches": taches,
        "propositions": propositions,
        "agents": agents,
        "journal": lignes_journal[:60],
        "projets": projets_info,
        "budget": {"depense": round(routeur_ia.depense_du_mois(racine=racine), 2),
                   "plafond": routeur_ia.plafond_mensuel()},
        "modules": [dict(nom=m["nom"], description=m.get("description", ""),
                         **modules.etat(m["nom"], racine)) for m in modules.decouvrir()],
    }


def cerveau(projet, racine=None):
    """
    Le cerveau d'UN projet, pour la 3D et l'aperçu 2D. Uniquement des titres et des
    liens, jamais le contenu des notes.
    - passif (mémoire) : notes = neurones cyan, synapses pondérées ;
    - actif (action)   : agents, tâches à faire, propositions en attente (ambre) ;
    - ponts            : liens actif → passif qui traversent le corps calleux.
    """
    if projet not in cc.lister_projets(racine):
        raise KeyError(f"Projet inconnu : {projet!r}")
    notes, liens = cc.titres_et_liens(projet, racine)
    titres = {n["titre"]: n["id"] for n in notes}
    passif = {
        "neurones": [{"id": f"n{n['id']}", "titre": n["titre"], "validee": n["validee"]}
                     for n in notes],
        "synapses": [{"a": f"n{l['source']}", "b": f"n{l['cible']}", "poids": round(l["poids"], 3)}
                     for l in liens],
    }
    e = cc.etat_projet(projet, racine)
    equipe = agents_mod.charger_tous(racine=racine)
    actif = {"neurones": [], "synapses": []}
    ponts = []
    for nom, a in equipe.items():
        actif["neurones"].append({"id": f"a:{nom}", "titre": nom, "type": "agent", "voie": a.voie})
    for t in e["taches"]:
        if t["statut"] not in orchestrateur.STATUTS_A_FAIRE:
            continue
        tid = f"t{t['id']}"
        actif["neurones"].append({"id": tid, "titre": t["titre"], "type": "tache",
                                  "statut": t["statut"], "planifiee": bool(t["contrat"])})
        if t["contrat"] and "planificateur" in equipe:
            actif["synapses"].append({"a": "a:planificateur", "b": tid, "poids": 0.6})
        if t["note_id"]:
            ponts.append({"actif": tid, "passif": f"n{t['note_id']}"})
    for p in e["propositions_en_attente"]:
        pid = f"p{p['id']}"
        actif["neurones"].append({"id": pid, "titre": p["titre"], "type": "proposition",
                                  "en_attente": True, "proposition": p["id"]})
        auteur = p["acteur"][6:] if p["acteur"].startswith("agent:") else None
        if auteur in equipe:
            actif["synapses"].append({"a": f"a:{auteur}", "b": pid, "poids": 0.5})
        if p["verification"] and "verificateur" in equipe:
            actif["synapses"].append({"a": "a:verificateur", "b": pid, "poids": 0.4})
        cibles = {titres[t] for t in p["liens"] if t in titres}
        if p.get("note_cible"):
            cibles.add(p["note_cible"])
        for nid in sorted(cibles):
            ponts.append({"actif": pid, "passif": f"n{nid}"})
    return {"projet": projet, "demo": cc.projet_demo(projet, racine),
            "sensible": e["sensible"], "passif": passif, "actif": actif, "ponts": ponts}


def simuler_nuit(projet, racine=None):
    """
    « Simuler une nuit » : une nuit d'oubli et d'apprentissage sur les synapses
    (oubli 0,02, apprentissage 0,10, archivage sous 0,05). Projets de DÉMO seulement,
    pour ne jamais vieillir la vraie mémoire par un clic.
    """
    if not cc.projet_demo(projet, racine):
        raise PermissionError("« Simuler une nuit » est réservé aux projets de démonstration.")
    nuit = synapses.prochaine_nuit(projet, racine)
    bilan = synapses.appliquer_oubli(projet, nuit, racine=racine, acteur="kayd (simulation)")
    cc.journal(projet, "nuit simulée depuis le cockpit",
               f"{bilan['renforcees']} renforcement(s), {bilan['archivees']} archivage(s)",
               date=nuit, racine=racine, acteur="kayd (simulation)")
    return dict(bilan, nuit=nuit.isoformat(),
                reglages={k: synapses.REGLAGES[k] for k in ("oubli", "apprentissage",
                                                             "seuil_archivage")})


def graphe(racine=None):
    """Uniquement titres et liens : jamais le contenu des notes."""
    resultat = []
    for p in cc.lister_projets(racine):
        notes, liens = cc.titres_et_liens(p, racine)
        resultat.append({"nom": p, "notes": notes, "liens": liens})
    return {"projets": resultat}


def lire_note(projet, note_id, racine=None):
    n = next((n for n in projets.lister_notes(projet, racine) if n["id"] == note_id), None)
    if n is None:
        raise KeyError("Note introuvable.")
    contenu = projets.lire_note(projet, note_id, racine)
    titres = {x["titre"]: x["id"] for x in projets.lister_notes(projet, racine)}
    liens = [{"titre": t, "id": titres.get(t)} for t in projets.trouver_liens(contenu)]
    retro = [{"titre": t, "id": titres.get(t)} for t in cc.retroliens(projet, note_id, racine)]
    return {"projet": projet, "id": n["id"], "titre": n["titre"], "contenu": contenu,
            "sensible": bool(n["sensible"]), "validee": bool(n.get("validee", 0)),
            "liens": liens, "retroliens": retro}


def lister_notes(projet, racine=None):
    return [{"id": n["id"], "titre": n["titre"], "sensible": bool(n["sensible"])}
            for n in projets.lister_notes(projet, racine)]


# ------------------------------------------------------------------
# Serveur HTTP
# ------------------------------------------------------------------

class Gestionnaire(BaseHTTPRequestHandler):
    jeton = ""
    racine = None

    def log_message(self, format, *args):  # silence dans le terminal
        pass

    # --- outils ---

    def _jeton_recu(self):
        q = parse_qs(urlparse(self.path).query)
        if "jeton" in q:
            return q["jeton"][0]
        if self.headers.get("X-Jeton"):
            return self.headers["X-Jeton"]
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return c[NOM_COOKIE].value if NOM_COOKIE in c else ""

    def _autorise(self):
        return hmac.compare_digest(self._jeton_recu() or "", self.jeton)

    def _envoyer(self, code, corps, type_="application/json; charset=utf-8", entetes=None):
        if not isinstance(corps, bytes):
            corps = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corps)

    def _refuser(self):
        page = ("<!doctype html><meta charset=utf-8><title>JARVIS</title>"
                "<body style='background:#000;color:#cfe6ff;font-family:monospace;padding:2em'>"
                "<h1>Accès protégé</h1><p>Ouvre le lien complet affiché dans le terminal "
                "(il contient le jeton d'accès).</p>").encode("utf-8")
        self._envoyer(401, page, "text/html; charset=utf-8")

    def _corps_json(self):
        taille = int(self.headers.get("Content-Length") or 0)
        if taille > 1_000_000:
            raise ValueError("Requête trop grosse.")
        return json.loads(self.rfile.read(taille) or b"{}")

    # --- routes ---

    def do_GET(self):
        url = urlparse(self.path)
        if not self._autorise():
            return self._refuser()
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path == "/":
                if "jeton" in q:  # on range le jeton dans un cookie puis on nettoie l'adresse
                    c = (f"{NOM_COOKIE}={self.jeton}; HttpOnly; SameSite=Strict; Path=/")
                    self.send_response(303)
                    self.send_header("Set-Cookie", c)
                    self.send_header("Location", "/")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                return self._envoyer(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/etat":
                return self._envoyer(200, etat(self.racine, q.get("projet")))
            if url.path == "/api/cerveau":
                return self._envoyer(200, cerveau(q["projet"], self.racine))
            if url.path == "/api/graphe":
                return self._envoyer(200, graphe(self.racine))
            if url.path == "/api/notes":
                return self._envoyer(200, lister_notes(q["projet"], self.racine))
            if url.path == "/api/note":
                return self._envoyer(200, lire_note(q["projet"], int(q["id"]), self.racine))
            self._envoyer(404, {"erreur": "Introuvable"})
        except Exception as e:
            self._envoyer(400, {"erreur": f"{type(e).__name__} : {e}"})

    def do_POST(self):
        url = urlparse(self.path)
        if not self._autorise():
            return self._envoyer(401, {"erreur": "Accès refusé"})
        try:
            d = self._corps_json()
            r = self.racine
            if url.path == "/api/proposition":
                if d["action"] == "valider":
                    res = cc.valider_proposition(d["projet"], int(d["id"]), racine=r)
                    return self._envoyer(200, {"ok": True, "cree": res})
                if d["action"] == "refuser":
                    cc.refuser_proposition(d["projet"], int(d["id"]), racine=r,
                                           raison=d.get("raison"))
                    return self._envoyer(200, {"ok": True})
                raise ValueError("Action inconnue.")
            if url.path == "/api/tache":
                statut = orchestrateur.terminer(d["projet"], int(d["id"]), bool(d["fait"]), racine=r)
                return self._envoyer(200, {"ok": True, "statut": statut})
            if url.path == "/api/tache/nouvelle":
                tid = projets.creer_tache(d["projet"], d["titre"].strip(),
                                          echeance=d.get("echeance") or None, racine=r,
                                          acteur="kayd")
                return self._envoyer(200, {"ok": True, "id": tid})
            if url.path == "/api/note":
                if d.get("id"):
                    cc.modifier_note_humaine(d["projet"], int(d["id"]), d["contenu"], racine=r)
                    nid = int(d["id"])
                else:
                    nid = cc.creer_note_humaine(d["projet"], d["titre"].strip(), d["contenu"],
                                                sensible=bool(d.get("sensible")), racine=r)
                return self._envoyer(200, {"ok": True, "id": nid})
            if url.path == "/api/projet":
                projets.creer_projet(d["nom"].strip(), racine=r, acteur="kayd")
                if d.get("sensible"):
                    cc.marquer_projet_sensible(d["nom"].strip(), racine=r)
                return self._envoyer(200, {"ok": True})
            if url.path == "/api/nuit":
                return self._envoyer(200, simuler_nuit(d["projet"], self.racine))
            if url.path == "/api/tour":
                return self._envoyer(200, orchestrateur.tour(racine=r))
            self._envoyer(404, {"erreur": "Introuvable"})
        except Exception as e:
            self._envoyer(400, {"erreur": f"{type(e).__name__} : {e}"})


def creer_serveur(port=8765, jeton=None, racine=None, hote="127.0.0.1"):
    jeton = jeton or reglages.lire("COCKPIT_JETON") or secrets.token_urlsafe(16)
    gestionnaire = type("GestionnaireJarvis", (Gestionnaire,), {"jeton": jeton, "racine": racine})
    serveur = ThreadingHTTPServer((hote, port), gestionnaire)
    serveur.jeton = jeton
    return serveur


def lancer(port=8765, ouvrir=True):
    serveur = creer_serveur(port)
    adresse = f"http://127.0.0.1:{serveur.server_address[1]}/?jeton={serveur.jeton}"
    print("Cockpit JARVIS prêt. Ouvre cette adresse dans ton navigateur :")
    print("   " + adresse)
    print("(Ctrl + C pour arrêter.)")
    if ouvrir:
        webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nCockpit arrêté.")
