"""
Interface web de JARVIS (marche 7) : un petit site qui tourne sur ta machine.

    python3 jarvis.py cockpit

- « / »         : l'interface « sphère » (second cerveau, conversation, hologrammes) ;
- « /cockpit »  : l'ancien cockpit à 4 écrans (toujours disponible).

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
from urllib.parse import parse_qs, urlencode, urlparse

RACINE_DEPOT = Path(__file__).resolve().parent.parent
if str(RACINE_DEPOT) not in sys.path:
    sys.path.insert(0, str(RACINE_DEPOT))

from noyau import agent as agents_mod  # noqa: E402
from noyau import corps_calleux as cc  # noqa: E402
from noyau import modules, orchestrateur, projets, reglages, routeur_ia, synapses  # noqa: E402

DOSSIER_INTERFACE = Path(__file__).resolve().parent
PAGE_COCKPIT = DOSSIER_INTERFACE / "cockpit.html"
PAGE = PAGE_COCKPIT                      # (nom gardé pour compatibilité)
DOSSIER_SPHERE = DOSSIER_INTERFACE / "sphere"
PAGE_SPHERE = DOSSIER_SPHERE / "index.html"
NOM_COOKIE = "jarvis_jeton"
TYPES_FICHIERS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                  ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                  ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml",
                  ".png": "image/png"}


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
    compte_agents, dernier_agent = {}, {}
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
                dernier_agent[nom] = l
    lignes_journal.sort(key=lambda l: (l["date"], l.get("n", 0)), reverse=True)
    agents = []
    for n, a in agents_mod.charger_tous(racine=racine).items():
        d = dernier_agent.get(n)
        agents.append(dict(a.decrire(), actions=compte_agents.get(n, 0),
                           etat="actif" if d else "en veille",
                           dernier=d["evenement"] if d else None))
    appels_mcp = [l for l in lignes_journal if l["acteur"] == "claude (MCP)"][:5]
    if projet is None:
        maintenant = orchestrateur.prochaine_action(racine)
    else:
        maintenant = next((t["contrat"] for t in orchestrateur.taches_a_faire(racine)
                           if t["projet"] == projet and t["contrat"]), None)
    return {
        "projet": projet,
        "mode_ia": routeur_ia.mode_ia(),
        "corps_calleux": appels_mcp,
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
    actif["neurones"].append({"id": "o", "titre": "orchestrateur", "type": "orchestrateur"})
    for nom, a in equipe.items():
        actif["neurones"].append({"id": f"a:{nom}", "titre": nom, "type": "agent", "voie": a.voie})
        actif["synapses"].append({"a": "o", "b": f"a:{nom}", "poids": 0.3})
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
    toutes = synapses.lister_synapses(projet, racine)
    compteurs = {"passifs": len(passif["neurones"]),
                 "actifs": sum(1 for n in actif["neurones"] if n["type"] != "orchestrateur"),
                 "synapses": len(passif["synapses"]),
                 "archivees": sum(1 for x in toutes if x["archivee"]),
                 "en_attente": len(e["propositions_en_attente"])}
    return {"projet": projet, "demo": cc.projet_demo(projet, racine), "compteurs": compteurs,
            "sensible": e["sensible"], "passif": passif, "actif": actif, "ponts": ponts}


def simuler_nuit(projet, racine=None):
    """
    « Simuler une nuit » : une VRAIE nuit complète pour le projet de démo : oubli 0,02,
    apprentissage 0,10, archivage sous 0,05, puis tri, analyse, rêve et réveil.
    Projets de DÉMO seulement, pour ne jamais vieillir la vraie mémoire par un clic.
    """
    from noyau import sommeil
    if not cc.projet_demo(projet, racine):
        raise PermissionError("« Simuler une nuit » est réservé aux projets de démonstration.")
    r = sommeil.nuit_simulee(projet, racine)
    cc.journal(projet, "nuit simulée depuis le cockpit", f"nuit du {r['nuit']}",
               racine=racine, acteur="kayd (simulation)")
    return dict(r, reglages={k: synapses.REGLAGES[k] for k in ("oubli", "apprentissage",
                                                                "seuil_archivage")})


def idee_du_jour(projet, racine=None):
    from noyau import reve
    return reve.idee_du_jour(projet, racine)


def decider_reve(projet, rid, decision, raison=None, racine=None):
    from noyau import reve
    if decision not in ("garder", "rejeter"):
        raise ValueError("Décision inconnue.")
    return (reve.garder if decision == "garder" else reve.rejeter)(projet, int(rid), raison,
                                                                   racine=racine)


def sphere(racine=None):
    """
    Toute la mémoire pour la sphère : un neurone par note, une synapse par lien pondéré,
    une région par projet. Uniquement titres, identifiants et poids, jamais le contenu.
    Les propositions en attente (jaune) et les synapses de rêve (5 au plus par projet)
    accompagnent chaque projet.
    """
    from noyau import reve
    resultat, tous_demo = [], True
    for p in cc.lister_projets(racine):
        notes, liens = cc.titres_et_liens(p, racine)
        sensibles = {n["id"] for n in projets.lister_notes(p, racine) if n["sensible"]}
        degre = {}
        for l in liens:
            for x in (l["source"], l["cible"]):
                degre[x] = degre.get(x, 0) + 1
        titres = {n["titre"]: n["id"] for n in notes}
        propositions = []
        for prop in cc.lister_propositions(p, "en attente", racine):
            cibles = {titres[t] for t in prop["liens"] if t in titres}
            if prop.get("note_cible"):
                cibles.add(prop["note_cible"])
            propositions.append({"id": prop["id"], "titre": prop["titre"], "type": prop["type"],
                                 "acteur": prop["acteur"], "notes": sorted(cibles)})
        reves = []
        for r in reve.lister(p, racine=racine)[-5:]:
            src = [int(x) for x in r["sources"]]
            for a, b in zip(src, src[1:]):
                reves.append({"a": a, "b": b, "idee": r["idee"][:120], "statut": r["statut"]})
        demo = cc.projet_demo(p, racine)
        tous_demo = tous_demo and demo
        resultat.append({
            "nom": p, "sensible": cc.projet_sensible(p, racine), "demo": demo,
            "neurones": [{"id": n["id"], "titre": n["titre"], "validee": n["validee"],
                          "sensible": n["id"] in sensibles, "liens": degre.get(n["id"], 0)}
                         for n in notes],
            "synapses": [{"a": l["source"], "b": l["cible"], "poids": round(l["poids"], 3)}
                         for l in liens],
            "reves": reves[:5], "propositions": propositions,
        })
    return {"projets": resultat, "demo": bool(resultat) and tous_demo,
            "mode_ia": routeur_ia.mode_ia(),
            "compteurs": {"neurones": sum(len(x["neurones"]) for x in resultat),
                          "synapses": sum(len(x["synapses"]) for x in resultat)}}


def a_valider(racine=None):
    """Les propositions en attente de tous les projets (le widget « À valider »)."""
    return [{"projet": p, "id": prop["id"], "titre": prop["titre"], "type": prop["type"],
             "acteur": prop["acteur"], "raison": prop["raison"], "creee_le": prop["creee_le"]}
            for p in cc.lister_projets(racine)
            for prop in cc.lister_propositions(p, "en attente", racine)]


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

    def _fichier_statique(self, relatif):
        """Sert un fichier de interface/sphere/, sans jamais sortir de ce dossier."""
        base = DOSSIER_SPHERE.resolve()
        chemin = (base / relatif).resolve()
        if base not in chemin.parents or not chemin.is_file() \
                or chemin.suffix not in TYPES_FICHIERS or "tests" in chemin.relative_to(base).parts:
            return self._envoyer(404, {"erreur": "Introuvable"})
        self._envoyer(200, chemin.read_bytes(), TYPES_FICHIERS[chemin.suffix])

    # --- routes ---

    def do_GET(self):
        url = urlparse(self.path)
        if not self._autorise():
            return self._refuser()
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            est_page = url.path in ("/", "/cockpit") or url.path.endswith(".html")
            if est_page and "jeton" in q:
                # On range le jeton dans un cookie, puis on nettoie l'adresse (sans le jeton).
                autres = urlencode({k: v for k, v in q.items() if k != "jeton"})
                c = f"{NOM_COOKIE}={self.jeton}; HttpOnly; SameSite=Strict; Path=/"
                self.send_response(303)
                self.send_header("Set-Cookie", c)
                self.send_header("Location", url.path + ("?" + autres if autres else ""))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if url.path == "/":
                return self._envoyer(200, PAGE_SPHERE.read_bytes(), "text/html; charset=utf-8")
            if url.path == "/cockpit":
                return self._envoyer(200, PAGE_COCKPIT.read_bytes(), "text/html; charset=utf-8")
            if url.path.startswith("/sphere/"):
                return self._fichier_statique(url.path[len("/sphere/"):])
            if url.path == "/api/sphere":
                return self._envoyer(200, sphere(self.racine))
            if url.path == "/api/a_valider":
                return self._envoyer(200, a_valider(self.racine))
            if url.path == "/api/systeme":
                from interface import fournisseurs
                return self._envoyer(200, fournisseurs.machine())
            if url.path == "/api/depenses":
                from interface import fournisseurs
                return self._envoyer(200, fournisseurs.depenses(self.racine))
            if url.path == "/api/journal_du_jour":
                from interface import fournisseurs
                return self._envoyer(200, fournisseurs.journal_du_jour(self.racine))
            if url.path == "/api/affichage":
                from noyau import affichage
                return self._envoyer(200, affichage.lister(int(q.get("apres", 0)),
                                                           racine=self.racine))
            if url.path == "/api/etat":
                return self._envoyer(200, etat(self.racine, q.get("projet")))
            if url.path == "/api/reve":
                return self._envoyer(200, idee_du_jour(q["projet"], self.racine))
            if url.path == "/api/journal":
                apres = int(q.get("apres", 0))
                lignes = [dict(l, projet=q["projet"]) for l in projets.lire_journal(q["projet"], self.racine)
                          if l["n"] > apres]
                return self._envoyer(200, lignes[-200:])
            if url.path == "/api/ia":
                from noyau import routeur
                return self._envoyer(200, routeur.etat(self.racine))
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
            if url.path == "/api/reve":
                r = decider_reve(d["projet"], d["id"], d["decision"], d.get("raison"), self.racine)
                return self._envoyer(200, {"ok": True, "statut": r["statut"]})
            if url.path == "/api/nuit":
                return self._envoyer(200, simuler_nuit(d["projet"], self.racine))
            if url.path == "/api/demander":
                from interface import conversation
                return self._envoyer(200, conversation.repondre(d.get("texte", ""), d.get("projet"),
                                                                self.racine))
            if url.path == "/api/affichage/action":
                from interface import conversation
                from noyau import affichage
                res = affichage.recevoir_action(
                    int(d["widget"]), d["action"], d.get("params") or {},
                    lambda ev, a, p: conversation.rafraichir(ev, a, p, self.racine),
                    racine=self.racine)
                return self._envoyer(200, res)
            if url.path == "/api/tour":
                return self._envoyer(200, orchestrateur.tour(racine=r))
            self._envoyer(404, {"erreur": "Introuvable"})
        except Exception as e:
            self._envoyer(400, {"erreur": f"{type(e).__name__} : {e}"})


def creer_serveur(port=8765, jeton=None, racine=None, hote="127.0.0.1"):
    jeton = jeton or reglages.lire("COCKPIT_JETON") or secrets.token_urlsafe(16)
    gestionnaire = type("GestionnaireJarvis", (Gestionnaire,), {"jeton": jeton, "racine": racine})
    serveur = ThreadingHTTPServer((hote, port), gestionnaire)
    from interface import fournisseurs
    fournisseurs.demarrer_session(racine)
    serveur.jeton = jeton
    return serveur


def lancer(port=8765, ouvrir=True):
    serveur = creer_serveur(port)
    adresse = f"http://127.0.0.1:{serveur.server_address[1]}/?jeton={serveur.jeton}"
    print("JARVIS prêt. Ouvre cette adresse dans ton navigateur :")
    print("   " + adresse)
    print("(Ctrl + C pour arrêter.)")
    if ouvrir:
        webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nCockpit arrêté.")
