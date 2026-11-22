"""
Sommeil et rêve de JARVIS (marche 6).

    python3 jarvis.py dormir            tous les projets
    python3 jarvis.py dormir Demo-A     un seul projet

Commande AUTONOME : n'importe quel déclencheur peut l'appeler (aujourd'hui la
tâche planifiée du Mac, plus tard un mode nuit ou un serveur). Règle des 24 h :
un projet qui a déjà rêvé dans les dernières 24 heures est laissé tranquille.

Pour chaque projet (chacun rêve seul, l'étanchéité est conservée), 4 phases :

    1. tri      code d'abord (oubli des synapses, archivage sous le seuil),
                puis l'IA repère doublons, notes orphelines ou périmées.
                Toute modification de note devient une PROPOSITION (garde d'écriture).
    2. analyse  résumé du projet entier (code puis IA, dans la limite de jetons des
                réglages) et synthèses proposées pour les groupes de notes très liées.
    3. rêve     tirage au hasard de paires ou triplets de notes ÉLOIGNÉES ;
                une IA créative (température haute) imagine les idées candidates.
    4. réveil   une IA rigoureuse note chaque idée selon tes contraintes et ne
                garde que la meilleure (idees_par_projet par nuit).

Règles :
- toute demande à l'IA passe par le routeur IA (noyau/routeur_ia.py), qui
  utilise d'abord le modèle local (Ollama) s'il est disponible ;
- notes sensibles : seulement vers le modèle local ; sans lui, exclues du rêve ;
- cloud payant : seulement pour le réveil, si cloud_pour_reveil=true, et dans la
  limite du budget IA mensuel du routeur (pas de plafond propre au rêve) ;
- le sommeil ne fait que PROPOSER : il n'écrit jamais dans les notes ;
- chaque phase écrit une ligne au journal du projet.
"""

import json
import re
import sys
from pathlib import Path

from noyau import agent as agents_mod
from datetime import date as date_, datetime, time, timedelta

from noyau import corps_calleux, projets, reglages, routeur_ia, synapses
from noyau.outils import jour, similarite

REGLAGES_SOMMEIL = {
    "seuil_groupe": 0.25,      # poids minimum pour que deux notes soient « très liées »
    "taille_min_groupe": 3,    # nombre minimum de notes pour proposer une synthèse
    "tri_max_propositions": 3,  # au plus 3 propositions de tri par projet et par nuit
}


# ------------------------------------------------------------------
# La nuit : compteur d'appels et accès au routeur IA
# ------------------------------------------------------------------

class Nuit:

    def __init__(self, maintenant, racine=None, fournisseurs=None):
        self.maintenant = maintenant
        self.date = jour(maintenant)
        self.racine, self.fournisseurs = racine, fournisseurs
        self.cout = 0.0
        self.appels = 0
        self.local = self.modele_local_disponible()

    def modele_local_disponible(self):
        f = (self.fournisseurs or routeur_ia.fournisseurs_par_defaut()).get("local")
        return bool(f and f.disponible())

    def ia(self, tache, demande, difficulte="courante", sensible=False, temperature=None,
           payant_autorise=False):
        """
        Demande à l'IA via le routeur ; « demande » est un dict envoyé en JSON.
        payant_autorise : le cloud payant n'est permis que si on le dit (phase réveil).
        Le budget IA mensuel du routeur s'applique toujours.
        """
        texte = json.dumps(demande, ensure_ascii=False)
        if sensible and not self.local:
            raise RuntimeError("Note sensible sans modèle local : envoi refusé.")  # garde-fou
        r = routeur_ia.demander_ia(tache, texte, difficulte, sensible, date=self.date,
                                   racine=self.racine, fournisseurs=self.fournisseurs,
                                   temperature=temperature, payant_autorise=payant_autorise)
        self.cout += r["cout_estime"]
        self.appels += 1
        r["donnees"] = lire_json(r["reponse"])
        return r


def lire_json(texte):
    """Extrait l'objet JSON d'une réponse d'IA (même entouré de texte). None si illisible."""
    m = re.search(r"\{.*\}", texte or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class Contexte:
    """Tout ce dont une phase a besoin pour un projet."""

    def __init__(self, projet, nuit, reglages_sommeil):
        self.projet, self.nuit = projet, nuit
        self.date, self.racine = nuit.date, nuit.racine
        self.maintenant = nuit.maintenant
        self.r = reglages_sommeil
        self.sensible_projet = corps_calleux.projet_sensible(projet, self.racine)
        self.local = nuit.local  # modèle local (Ollama) disponible cette nuit ?
        self.agent = agents_mod.charger("synthetiseur", racine=self.racine, date=self.date)

    def journal(self, evenement, raison=None):
        corps_calleux.journal(self.projet, evenement, raison, date=self.date,
                              racine=self.racine, acteur="sommeil")

    def notes(self):
        """Toutes les notes du projet (id, titre, extrait, poids, sensible…)."""
        return corps_calleux.se_souvenir(self.projet, "", 50, racine=self.racine)

    def est_sensible(self, note):
        return self.sensible_projet or bool(note["sensible"])

    def notes_partageables(self):
        """
        Notes qui peuvent être envoyées à l'IA pendant le sommeil :
        - avec un modèle local disponible : toutes (les sensibles iront au local) ;
        - sans modèle local : jamais les sensibles (elles sont exclues du rêve).
        """
        if self.local:
            return self.notes()
        return [n for n in self.notes() if not self.est_sensible(n)]

    def contient_sensible(self, notes):
        """Vrai si l'envoi contient une note sensible : le routeur n'utilisera que le local."""
        return any(self.est_sensible(n) for n in notes)


# ------------------------------------------------------------------
# Outils communs aux phases
# ------------------------------------------------------------------

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


def deja_propose(projet, marque, racine):
    """Vrai si une proposition (quel que soit son statut) porte déjà cette marque."""
    return any((p["raison"] or "").startswith(marque + " ") or (p["raison"] or "") == marque
               for p in corps_calleux.lister_propositions(projet, racine=racine))


# ------------------------------------------------------------------
# Phase 1 : tri
# ------------------------------------------------------------------

def phase_tri(ctx):
    # 1. Le code d'abord : oubli des synapses et archivage sous le seuil.
    oubli = synapses.appliquer_oubli(ctx.projet, ctx.date, racine=ctx.racine)
    ctx.journal("sommeil · tri (code)",
                f"oubli appliqué : {oubli['renforcees']} renforcement(s), "
                f"{oubli['archivees']} archivage(s)")

    # 2. Puis une IA légère : doublons, notes orphelines, notes périmées.
    notes = ctx.notes_partageables()
    if not notes:
        ctx.journal("sommeil · tri (IA)", "rien à envoyer : aucune note partageable "
                    "(sans modèle local, les notes sensibles sont exclues)")
        return dict(oubli, tri_propositions=[])
    liens = {}
    for s in synapses.lister_synapses(ctx.projet, ctx.racine, avec_archivees=False):
        for nid in (s["note_source"], s["note_cible"]):
            liens[nid] = liens.get(nid, 0) + 1
    dates = {n["id"]: n["modifiee_le"][:10] for n in projets.lister_notes(ctx.projet, ctx.racine)}
    peremption = int(reglages.lire_nombre("tri_peremption_jours", 90))
    demande = {
        "consigne": ("Repère dans ces notes : les doublons (deux notes qui disent la même chose), "
                     "les notes orphelines (aucun lien) et les notes périmées (pas modifiées "
                     f"depuis plus de {peremption} jours). Réponds en JSON : "
                     '{"doublons": [{"notes": [id_ancienne, id_recente], "raison": "..."}], '
                     '"orphelines": [{"note": id, "raison": "..."}], '
                     '"perimees": [{"note": id, "raison": "..."}]}'),
        "aujourd_hui": ctx.date.isoformat(),
        "peremption_jours": peremption,
        "notes": [{"id": n["id"], "titre": n["titre"], "extrait": n["extrait"][:200],
                   "liens_actifs": liens.get(n["id"], 0), "modifiee_le": dates[n["id"]]}
                  for n in notes],
    }
    reponse = ctx.nuit.ia("trier", demande, "courante", sensible=ctx.contient_sensible(notes),
                          temperature=0.1)
    d = reponse["donnees"] or {}
    proposees = _proposer_tri(ctx, notes, d)
    ctx.journal("sommeil · tri (IA)",
                f"{len(d.get('doublons', []))} doublon(s), {len(d.get('orphelines', []))} "
                f"orpheline(s), {len(d.get('perimees', []))} périmée(s) repéré(s) ; "
                f"{len(proposees)} proposition(s) de modification (à valider)")
    return dict(oubli, tri_propositions=proposees)


def _proposer_tri(ctx, notes, d):
    """Transforme les trouvailles de l'IA en propositions de modification (jamais d'écriture)."""
    par_id = {n["id"]: n for n in notes}
    jour_txt = ctx.date.isoformat()
    candidats = []  # (marque, note_cible, nouveau_contenu, raison lisible)
    for item in d.get("doublons", []):
        ids = [i for i in (item.get("notes") or []) if i in par_id]
        if len(ids) != 2 or ids[0] == ids[1]:
            continue
        a, b = sorted(ids)
        texte = projets.lire_note(ctx.projet, b, ctx.racine)
        candidats.append((f"tri:doublon:{a},{b}", b,
                          f"> ⚠ Doublon probable de [[{par_id[a]['titre']}]] (repéré pendant le "
                          f"sommeil du {jour_txt}). À fusionner à la main si besoin.\n\n{texte}",
                          item.get("raison") or "doublon probable"))
    for item in d.get("orphelines", []):
        i = item.get("note")
        if i not in par_id:
            continue
        autres = [n for n in notes if n["id"] != i]
        voisin = max(autres, key=lambda n: similarite(n["titre"] + " " + n["extrait"],
                                                      par_id[i]["titre"] + " " + par_id[i]["extrait"]),
                     default=None)
        texte = projets.lire_note(ctx.projet, i, ctx.racine)
        suggestion = f", par exemple à [[{voisin['titre']}]]" if voisin else ""
        candidats.append((f"tri:orpheline:{i}", i,
                          f"{texte.rstrip()}\n\n> Note isolée (sommeil du {jour_txt}) : "
                          f"à relier{suggestion}.\n",
                          item.get("raison") or "note sans aucun lien"))
    for item in d.get("perimees", []):
        i = item.get("note")
        if i not in par_id:
            continue
        texte = projets.lire_note(ctx.projet, i, ctx.racine)
        candidats.append((f"tri:perimee:{i}", i,
                          f"> ⚠ À revoir : note ancienne (sommeil du {jour_txt}).\n\n{texte}",
                          item.get("raison") or "note pas modifiée depuis longtemps"))

    # Priorité : doublons, puis notes périmées, puis notes orphelines.
    ordre = {"doublon": 0, "perimee": 1, "orpheline": 2}
    candidats.sort(key=lambda c: ordre[c[0].split(":")[1]])
    proposees = []
    for marque, cible, contenu, raison in candidats:
        if len(proposees) >= ctx.r["tri_max_propositions"]:
            break
        if deja_propose(ctx.projet, marque, ctx.racine):
            continue  # déjà proposé (même refusé) : on ne répète pas
        pid = ctx.agent.proposer(ctx.projet, "modification", contenu,
                                 titre=f"Tri : « {par_id[cible]['titre']} »",
                                 raison=f"{marque} · {raison}", note_cible=cible)
        proposees.append(pid)
    return proposees


# ------------------------------------------------------------------
# Phase 2 : analyse
# ------------------------------------------------------------------

def statistiques(ctx):
    """Le portrait du projet, calculé par le code seul (aucune IA)."""
    notes = ctx.notes()
    toutes_syn = synapses.lister_synapses(ctx.projet, ctx.racine)
    actives = [s for s in toutes_syn if not s["archivee"]]
    etat = corps_calleux.etat_projet(ctx.projet, ctx.racine)
    partageables = ctx.notes_partageables()
    return {
        "notes": len(notes),
        "notes_sensibles": sum(1 for n in notes if n["sensible"]) if not ctx.sensible_projet
        else len(notes),
        "notes_validees": sum(1 for n in notes if n["validee"]),
        "synapses_actives": len(actives),
        "synapses_archivees": len(toutes_syn) - len(actives),
        "poids_moyen": round(sum(s["poids"] for s in actives) / len(actives), 3) if actives else 0,
        "notes_centrales": [n["titre"] for n in sorted(partageables, key=lambda n: -n["poids"])[:5]
                            if n["poids"] > 0],
        "taches_a_faire": sum(1 for t in etat["taches"] if t["statut"] in ("à faire", "pas fait")),
        "taches_faites": sum(1 for t in etat["taches"] if t["statut"] == "fait"),
        "propositions_en_attente": len(etat["propositions_en_attente"]),
        "groupes_tres_lies": len(trouver_groupes(ctx.projet, ctx.racine, ctx.r)),
    }


def demande_resume(stats, notes, max_jetons):
    """
    Prépare la demande de résumé sans dépasser max_jetons (≈ 4 caractères par jeton) :
    on retire d'abord les notes les moins reliées, puis on raccourcit les extraits.
    """
    notes = sorted(notes, key=lambda n: -n["poids"])
    limite = max_jetons * 4
    taille_extrait = 200

    def construire():
        return {"consigne": ("Résume ce projet en 5 phrases au plus : où il en est, ce qui "
                             "avance, ce qui bloque, et la prochaine étape utile."),
                "statistiques": stats,
                "notes": [{"titre": n["titre"], "extrait": n["extrait"][:taille_extrait]}
                          for n in notes]}

    demande = construire()
    while len(json.dumps(demande, ensure_ascii=False)) > limite:
        if taille_extrait > 60:
            taille_extrait -= 40
        elif notes:
            notes.pop()
        else:
            break  # les statistiques seules : toujours petites
        demande = construire()
    return demande


def phase_analyse(ctx):
    # 1. Résumé du projet entier : code (statistiques) puis IA légère.
    stats = statistiques(ctx)
    max_jetons = int(reglages.lire_nombre("tokens_max_analyse", 1500))
    a_envoyer = ctx.notes_partageables()
    demande = demande_resume(stats, a_envoyer, max_jetons)
    texte = json.dumps(demande, ensure_ascii=False)
    if ctx.sensible_projet and not ctx.local:
        # Projet sensible sans modèle local : rien ne sort, même pas les statistiques.
        texte = ""
        resume = (f"Résumé par le code seul (projet sensible, pas de modèle local) : "
                  f"{stats['notes']} note(s), {stats['synapses_actives']} synapse(s) active(s), "
                  f"{stats['taches_a_faire']} tâche(s) à faire, "
                  f"{stats['propositions_en_attente']} proposition(s) en attente.")
    else:
        reponse = ctx.nuit.ia("resumer", demande, "courante",
                              sensible=ctx.contient_sensible(a_envoyer), temperature=0.3)
        resume = (reponse["donnees"] or {}).get("resume") or reponse["reponse"]
    conn = projets._connexion(ctx.projet, ctx.racine)
    try:
        with conn:
            conn.execute("INSERT INTO analyses (date, resume, stats, jetons_envoyes) "
                         "VALUES (?, ?, ?, ?)",
                         (ctx.date.isoformat(), resume, json.dumps(stats, ensure_ascii=False),
                          len(texte) // 4))
    finally:
        conn.close()
    ctx.journal("sommeil · analyse (résumé)",
                f"{stats['notes']} note(s), {stats['synapses_actives']} synapse(s) active(s) ; "
                f"résumé de {len(resume)} caractères, {len(texte) // 4} jeton(s) envoyé(s) "
                f"sur {max_jetons} permis")

    # 2. Synthèses proposées pour les groupes de notes très liées.
    notes = {n["id"]: n for n in ctx.notes_partageables()}
    proposees = []
    for g in trouver_groupes(ctx.projet, ctx.racine, ctx.r):
        signature = ",".join(str(i) for i in g["notes"])
        if deja_propose(ctx.projet, f"groupe {signature} :", ctx.racine):
            continue
        membres = [notes[i] for i in g["notes"] if i in notes]
        if len(membres) < ctx.r["taille_min_groupe"]:
            continue  # groupe surtout fait de notes sensibles, sans modèle local : on passe
        titres = [m["titre"] for m in membres]
        sensible = ctx.contient_sensible(membres)
        demande = {"consigne": "Résume en deux phrases ce qui relie ces notes.",
                   "notes": [{"titre": m["titre"], "extrait": m["extrait"]} for m in membres]}
        reponse = ctx.nuit.ia("synthetiser", demande, "courante", sensible)
        resume = (reponse["donnees"] or {}).get("resume") or reponse["reponse"]
        contenu = (f"# Synthèse : {', '.join(titres)}\n\n{resume}\n\n"
                   "Notes regroupées :\n" + "\n".join(f"- [[{t}]]" for t in titres) + "\n")
        raison = (f"groupe {signature} : {len(titres)} notes très liées "
                  f"(poids moyen {g['poids_moyen']:.2f}) repérées pendant le sommeil")
        pid = ctx.agent.proposer(ctx.projet, "synthese", contenu, liens=titres,
                                 titre=f"Synthèse : {', '.join(titres)}"[:80], raison=raison)
        proposees.append(pid)
    ctx.journal("sommeil · analyse (synthèses)", f"{len(proposees)} synthèse(s) proposée(s)")
    return {"syntheses_proposees": proposees, "resume": resume}


def dernier_resume(projet, racine=None):
    """Le résumé de la dernière nuit (pour le cockpit), ou None."""
    conn = projets._connexion(projet, racine)
    try:
        r = conn.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return dict(r, stats=json.loads(r["stats"]))


from noyau import reve  # noqa: E402  (les phases du rêve sont dans noyau/reve.py)

PHASES = [("tri", phase_tri), ("analyse", phase_analyse), ("rêve", reve.phase_reve),
          ("réveil", reve.phase_reveil)]


# ------------------------------------------------------------------
# La nuit complète
# ------------------------------------------------------------------

def _instant(maintenant):
    """Accepte une date (prise à 3 h du matin), une date et heure, ou rien (maintenant)."""
    if maintenant is None:
        return datetime.now().replace(microsecond=0)
    if isinstance(maintenant, datetime):
        return maintenant
    if isinstance(maintenant, date_):
        return datetime.combine(maintenant, time(3, 0))
    texte = str(maintenant)
    return datetime.fromisoformat(texte) if "T" in texte or " " in texte \
        else datetime.combine(date_.fromisoformat(texte), time(3, 0))


def dernier_sommeil(projet, racine=None):
    """Début du dernier sommeil du projet (datetime), ou None."""
    conn = projets._connexion(projet, racine)
    try:
        r = conn.execute("SELECT debut FROM sommeils ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return datetime.fromisoformat(r["debut"]) if r else None


def a_reve_recemment(projet, maintenant, racine=None):
    """Règle des 24 h : vrai si le projet a déjà rêvé dans les 24 dernières heures."""
    dernier = dernier_sommeil(projet, racine)
    return dernier is not None and maintenant - dernier < timedelta(hours=24)


def _noter_sommeil(projet, maintenant, statut, appels, cout, racine):
    conn = projets._connexion(projet, racine)
    try:
        with conn:
            conn.execute("INSERT INTO sommeils (debut, statut, appels_ia, cout) "
                         "VALUES (?, ?, ?, ?)",
                         (maintenant.isoformat(timespec="seconds"), statut, appels, cout))
    finally:
        conn.close()


def dormir(maintenant=None, projet=None, racine=None, reglages=None, fournisseurs=None):
    """
    Fait rêver un projet (ou tous). Les projets ayant rêvé dans les 24 dernières
    heures sont ignorés. Renvoie un bilan :
    {"maintenant", "cout", "appels_ia", "arret", "ignores", "projets": {nom: {...}}}
    """
    maintenant = _instant(maintenant)
    r = dict(REGLAGES_SOMMEIL, **(reglages or {}))
    nuit = Nuit(maintenant, racine, fournisseurs)
    tous = corps_calleux.lister_projets(racine)
    if projet is not None and projet not in tous:
        raise KeyError(f"Projet inconnu : {projet!r}")
    cibles = [projet] if projet else tous
    bilan = {"maintenant": maintenant.isoformat(timespec="seconds"), "projets": {},
             "arret": None, "ignores": []}

    for p in cibles:
        if a_reve_recemment(p, maintenant, racine):
            bilan["ignores"].append(p)
            continue
        ctx = Contexte(p, nuit, r)
        res = {}
        appels_avant, cout_avant = nuit.appels, nuit.cout
        for nom, phase in PHASES:
            try:
                res.update(phase(ctx) or {})
            except routeur_ia.BudgetDepasse as e:
                bilan["arret"] = str(e)
                ctx.journal(f"sommeil · arrêt propre pendant la phase {nom}", str(e))
                break
        res.setdefault("syntheses_proposees", [])
        ctx.journal("sommeil terminé",
                    f"{res.get('renforcees', 0)} renforcement(s), "
                    f"{res.get('archivees', 0)} archivage(s), "
                    f"{len(res['syntheses_proposees'])} synthèse(s) proposée(s), "
                    f"{nuit.appels - appels_avant} appel(s) IA, "
                    f"coût {nuit.cout - cout_avant:.3f} €")
        _noter_sommeil(p, maintenant, "arrêté" if bilan["arret"] else "fait",
                       nuit.appels - appels_avant, nuit.cout - cout_avant, racine)
        bilan["projets"][p] = res
        if bilan["arret"]:
            break  # budget mensuel épuisé : on n'entame pas les projets suivants

    bilan["cout"] = round(nuit.cout, 4)
    bilan["appels_ia"] = nuit.appels
    return bilan


# ------------------------------------------------------------------
# Planification sur Mac (launchd)
# ------------------------------------------------------------------

ETIQUETTE = "com.jarvis.sommeil"


def plist_launchd(chemin_depot, dossier_donnees, python=None, intervalle_minutes=10):
    """
    Le fichier de réglage launchd (le planificateur intégré au Mac).
    - RunAtLoad : lancement à l'ouverture de session (Mac allumé le matin).
    - StartInterval : launchd relance la commande toutes les N minutes ; pendant la
      veille, rien ne tourne, et dès le RÉVEIL du Mac l'intervalle écoulé déclenche
      un lancement. La règle des 24 h fait que le rêve n'a lieu qu'une fois par jour.
    Rien ne touche à la veille du Mac (pas de pmset).
    """
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
        <string>--silencieux</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{depot}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>{int(intervalle_minutes) * 60}</integer>
    <key>StandardOutPath</key>
    <string>{journal}</string>
    <key>StandardErrorPath</key>
    <string>{journal}</string>
</dict>
</plist>
"""
