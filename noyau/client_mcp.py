"""
Petit client MCP (bibliothèque standard seulement).

Il parle au serveur MCP de JARVIS exactement comme Claude Desktop : il le lance,
lui envoie des messages JSON-RPC ligne par ligne et lit ses réponses.
Sert aux tests automatiques et à la démo.

    with ClientMCP(dossier="~/.jarvis/demo") as c:
        print(c.outils())                          # ['se_souvenir', 'proposer', 'activer', 'journal']
        print(c.appeler("se_souvenir", projet="Projet A", requete="budget"))
"""

import json
import os
import subprocess
import sys
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent
VERSION_PROTOCOLE = "2025-06-18"


class ErreurMCP(RuntimeError):
    """Le serveur a répondu par une erreur (outil en erreur ou message refusé)."""


class ClientMCP:

    def __init__(self, dossier=None, commande=None, env=None):
        env = dict(env or os.environ)
        if dossier:
            env["DOSSIER_DONNEES"] = str(Path(dossier).expanduser())
        self.commande = commande or [sys.executable, "-m", "noyau.corps_calleux"]
        self.processus = subprocess.Popen(self.commande, cwd=str(RACINE_DEPOT), env=env,
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self._id = 0
        self.info = None

    # --- échanges de base ---

    def _envoyer(self, message):
        self.processus.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.processus.stdin.flush()

    def demander(self, methode, params=None):
        self._id += 1
        self._envoyer({"jsonrpc": "2.0", "id": self._id, "method": methode,
                       "params": params or {}})
        while True:
            ligne = self.processus.stdout.readline()
            if not ligne:
                raise ErreurMCP("Le serveur MCP s'est arrêté sans répondre.")
            reponse = json.loads(ligne)
            if reponse.get("id") != self._id:
                continue  # une notification du serveur : on l'ignore
            if "error" in reponse:
                raise ErreurMCP(reponse["error"].get("message", "erreur"))
            return reponse["result"]

    def notifier(self, methode, params=None):
        self._envoyer({"jsonrpc": "2.0", "method": methode, "params": params or {}})

    # --- le protocole MCP ---

    def initialiser(self):
        self.info = self.demander("initialize", {
            "protocolVersion": VERSION_PROTOCOLE, "capabilities": {},
            "clientInfo": {"name": "jarvis-client-minimal", "version": "1.0"}})
        self.notifier("notifications/initialized")
        return self.info

    def outils(self):
        return [o["name"] for o in self.demander("tools/list")["tools"]]

    def appeler(self, nom, **arguments):
        """Appelle un outil. Renvoie la réponse décodée (JSON) ; lève ErreurMCP en cas d'erreur."""
        r = self.demander("tools/call", {"name": nom, "arguments": arguments})
        texte = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        if r.get("isError"):
            raise ErreurMCP(texte)
        try:
            return json.loads(texte)
        except json.JSONDecodeError:
            return texte

    def fermer(self):
        if self.processus.poll() is None:
            self.processus.stdin.close()
            try:
                self.processus.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.processus.kill()
        if self.processus.stdout:
            self.processus.stdout.close()

    def __enter__(self):
        self.initialiser()
        return self

    def __exit__(self, *exc):
        self.fermer()
