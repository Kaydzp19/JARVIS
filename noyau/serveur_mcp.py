"""
Serveur MCP de JARVIS (marche 3) : branche Claude (Desktop ou Code) au cerveau.

MCP (Model Context Protocol) est le standard qui permet à Claude d'utiliser
des outils extérieurs. Ici, les outils sont les 4 messages du corps calleux.

Fonctionnement : Claude lance ce programme et lui parle par l'entrée et la
sortie standard (une ligne de texte JSON par message, format JSON-RPC 2.0).
Écrit uniquement avec la bibliothèque standard : rien à installer.

Lancement : python3 jarvis.py mcp

Garde-fous :
- chaque appel est noté dans le journal du projet concerné ;
- le texte des notes sensibles est masqué (il partirait vers Claude en ligne) ;
- « proposer » ne fait que proposer : seul Kayd valide.
"""

import json
import sys
import traceback

from noyau import corps_calleux

VERSION_PROTOCOLE = "2025-06-18"
VERSIONS_CONNUES = ("2024-11-05", "2025-03-26", "2025-06-18")
INFO_SERVEUR = {"name": "jarvis", "version": "0.1.0"}

INSTRUCTIONS = (
    "Tu es branché au second cerveau de JARVIS. Chaque projet est étanche. "
    "Pour savoir ce que JARVIS sait d'un projet, appelle se_souvenir. "
    "Tu ne peux rien écrire directement dans les notes : utilise proposer, "
    "Kayd validera. Quand tu utilises plusieurs notes ensemble pour répondre, "
    "appelle activer avec leurs identifiants."
)


def _outils(racine=None):
    projets = corps_calleux.lister_projets(racine)
    liste = ", ".join(projets) if projets else "(aucun projet pour l'instant)"
    nom_projet = {"type": "string", "description": f"Nom du projet. Projets existants : {liste}"}
    return [
        {
            "name": "se_souvenir",
            "description": ("Cherche dans la mémoire d'un projet les notes pertinentes "
                            "(id, titre, extrait, poids). N'écrit rien. Requête vide = "
                            "les notes les plus reliées du projet."),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projet": nom_projet,
                    "requete": {"type": "string", "description": "Mots à chercher."},
                    "limite": {"type": "integer", "description": "Nombre maximum de notes (1 à 50).",
                               "default": 5},
                },
                "required": ["projet"],
            },
        },
        {
            "name": "proposer",
            "description": ("Propose une nouvelle note, synthèse ou tâche. Elle reste EN "
                            "ATTENTE jusqu'à la validation de Kayd. Rien n'est écrit avant."),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projet": nom_projet,
                    "type": {"type": "string", "enum": list(corps_calleux.TYPES_PROPOSITION)},
                    "contenu": {"type": "string", "description": "Texte en Markdown."},
                    "titre": {"type": "string", "description": "Titre (facultatif)."},
                    "note_cible": {"type": "integer",
                                   "description": "Pour une modification : id de la note visée "
                                                  "(le contenu remplace son texte)."},
                    "liens": {"type": "array", "items": {"type": "string"},
                              "description": "Titres des notes à relier avec [[...]]."},
                },
                "required": ["projet", "type", "contenu"],
            },
        },
        {
            "name": "activer",
            "description": ("Signale que des notes ont servi ensemble : renforce les "
                            "synapses entre notes validées (appliqué la nuit suivante)."),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projet": nom_projet,
                    "ids_notes": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["projet", "ids_notes"],
            },
        },
        {
            "name": "journal",
            "description": "Ajoute une ligne au journal du projet (événement et raison).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projet": nom_projet,
                    "evenement": {"type": "string"},
                    "raison": {"type": "string"},
                },
                "required": ["projet", "evenement"],
            },
        },
    ]


ACTEUR = "claude (MCP)"


def appeler_outil(nom, args, racine=None):
    """Exécute un outil et renvoie un résultat JSON-sérialisable."""
    projet = args.get("projet")
    if projet not in corps_calleux.lister_projets(racine):
        raise ValueError(f"Projet inconnu : {projet!r}.")
    if nom == "se_souvenir":
        resultat = corps_calleux.se_souvenir(projet, args.get("requete", ""),
                                             args.get("limite", 5), racine=racine,
                                             masquer_sensibles=True)
        trace = f"requête « {args.get('requete', '')} », {len(resultat)} note(s)"
    elif nom == "proposer":
        pid = corps_calleux.proposer(projet, args.get("type"), args.get("contenu"),
                                     args.get("liens"), titre=args.get("titre"),
                                     note_cible=args.get("note_cible"),
                                     racine=racine, acteur=ACTEUR,
                                     raison="proposé depuis Claude")
        resultat = {"proposition": pid, "statut": "en attente",
                    "message": "Proposition enregistrée. Kayd doit la valider."}
        trace = f"proposition {pid}"
    elif nom == "activer":
        resultat = corps_calleux.activer(projet, args.get("ids_notes", []), racine=racine,
                                         acteur=ACTEUR, raison="notes utilisées ensemble par Claude")
        trace = f"{resultat['activees']} synapse(s) activée(s)"
    elif nom == "journal":
        corps_calleux.journal(projet, args.get("evenement", ""), args.get("raison"),
                              racine=racine, acteur=ACTEUR)
        resultat = {"ok": True}
        trace = "ligne ajoutée"
    else:
        raise ValueError(f"Outil inconnu : {nom!r}.")
    if nom != "journal":
        corps_calleux.journal(projet, f"appel MCP : {nom}", trace, racine=racine, acteur=ACTEUR)
    return resultat


def traiter(message, racine=None):
    """Traite un message JSON-RPC. Renvoie la réponse (dict) ou None pour une notification."""
    methode = message.get("method")
    ident = message.get("id")
    if ident is None:  # notification : pas de réponse
        return None
    try:
        if methode == "initialize":
            demandee = (message.get("params") or {}).get("protocolVersion")
            version = demandee if demandee in VERSIONS_CONNUES else VERSION_PROTOCOLE
            resultat = {"protocolVersion": version,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": INFO_SERVEUR,
                        "instructions": INSTRUCTIONS}
        elif methode == "ping":
            resultat = {}
        elif methode == "tools/list":
            resultat = {"tools": _outils(racine)}
        elif methode == "tools/call":
            params = message.get("params") or {}
            try:
                donnees = appeler_outil(params.get("name"), params.get("arguments") or {}, racine)
                resultat = {"content": [{"type": "text",
                                         "text": json.dumps(donnees, ensure_ascii=False, indent=2)}],
                            "isError": False}
            except Exception as e:  # erreur de l'outil : renvoyée à Claude, pas un plantage
                resultat = {"content": [{"type": "text", "text": f"Erreur : {e}"}],
                            "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": ident,
                    "error": {"code": -32601, "message": f"Méthode inconnue : {methode}"}}
        return {"jsonrpc": "2.0", "id": ident, "result": resultat}
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": str(e)}}


def servir(entree=None, sortie=None, racine=None):
    """Boucle principale : lit une ligne JSON, répond une ligne JSON."""
    entree = entree or sys.stdin
    sortie = sortie or sys.stdout
    print("JARVIS MCP : prêt.", file=sys.stderr)
    for ligne in entree:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            message = json.loads(ligne)
        except json.JSONDecodeError:
            reponse = {"jsonrpc": "2.0", "id": None,
                       "error": {"code": -32700, "message": "JSON illisible"}}
        else:
            reponse = traiter(message, racine)
        if reponse is not None:
            sortie.write(json.dumps(reponse, ensure_ascii=False) + "\n")
            sortie.flush()


if __name__ == "__main__":
    servir()
