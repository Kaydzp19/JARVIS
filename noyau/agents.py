"""
Les agents de JARVIS (nom court) : voir noyau/agent.py pour le détail.

Un agent = un fichier de réglage dans noyau/agents/<nom>.json :
une consigne + la liste des SEULS outils permis (se_souvenir, proposer,
activer, journal, ia). Aucun outil ne permet d'écrire, publier, payer ou
supprimer : un agent ne peut que PROPOSER.
"""

from noyau.agent import (DOSSIER_AGENTS, OUTILS_PERMIS, VOIES, Agent,  # noqa: F401
                         OutilInterdit, charger, charger_tous)
