# Rapport final · Prototype n°1 de JARVIS

Branche `prototype-1`, 22 novembre 2026. Rien n'a été poussé, fusionné ni supprimé
pendant cette session : tout est en commits locaux, en attente de l'accord de Kayd.

## 1. État de départ

- Branche la plus avancée : `prototype-1` (elle contient `marche-1-projets`, `marche-2-synapses`,
  `prototype` et `marche-6-reve` ; `main` n'a en plus que des commits de fusion).
- Tests vérifiés avant de commencer : **121 réussis** sur `marche-6-reve`, **147 réussis** sur
  `prototype-1`.
- Déjà en place : projets étanches, notes, synapses, journal, sommeil et rêve (4 phases, règle des
  24 h), routeur IA (mode simulé, Gemini et Claude branchés en mode réel, Ollama), serveur MCP à
  4 messages, orchestrateur et agents, garde d'écriture (`python -m noyau.valider`), module de
  notifications, première interface.
- Manquait : la recherche plein texte (FTS5), un vrai client MCP pour les tests, l'entrée
  `noyau/routeur.py`, des propositions pour chacune des 4 voies, des tests dédiés aux garde-fous,
  les notifications en console, la nuit complète depuis l'interface, l'interface conforme aux
  deux maquettes (écrans, journal en direct), une démo de bout en bout, ce rapport.

## 2. Ce qui a été construit, brique par brique (un commit chacune)

| Brique | Ce qui a été ajouté ou complété |
|---|---|
| 1 · Mémoire | Recherche plein texte **FTS5** (titres et contenus, sans accents ni majuscules, préfixes, titre plus important que le texte, index reconstruit tout seul pour une ancienne base, requêtes dangereuses neutralisées). `se_souvenir` classe par pertinence FTS5 puis par force des synapses. |
| 2 · Corps calleux | `python -m noyau.corps_calleux` lance le serveur MCP. Nouveau **client MCP minimal** (`noyau/client_mcp.py`) qui lance le serveur comme Claude Desktop ; une session complète avec les 4 messages est testée automatiquement, chaque appel est journalisé, les erreurs restent propres. |
| 3 · Routeur | `noyau/routeur.py` : `demander_ia(tache, difficulte, sensible)`, détection d'Ollama (sans jamais l'interroger), état des IA (mode, clés présentes, budget restant). Test qui **prouve** qu'une note sensible ne part jamais vers une offre gratuite. Plafond de 5 €/mois qui bloque l'appel. |
| 4 · Actif | Les 4 voies **proposent** : planifier (une tâche quand un projet n'en a plus), proposer (une note depuis une idée rêvée gardée), comparer (deux notes très proches), vérifier (liens `[[...]]` cassés, en plus des propositions). L'orchestrateur réagit à ces événements, l'IA seulement quand un événement le demande. Statut d'une proposition acceptée : « validée ». `noyau/agents.py`. Tests des **garde-fous** : aucun outil d'agent pour écrire, publier, payer ou supprimer ; types dangereux refusés ; rien d'écrit avant `python -m noyau.valider`, puis écriture réelle et ligne de journal ; le noyau ne supprime jamais une note. |
| 5 · Modules | Le module `notifications` annonce Fait / Pas fait **dans la console**. Un module n'écrit que ce que sa fiche déclare (console, journal, boîte). Activer puis retirer le module ne touche pas le noyau. |
| 6 · Sommeil | « Simuler une nuit » lance une **vraie nuit complète** (projets de démo). Parcours testé de bout en bout : Claude active des notes par MCP, la nuit les renforce et propose une synthèse, validée comme les autres, jamais reproposée. |
| 7 · Interface | Quatre écrans selon les maquettes et la palette : **Cerveau 3D** (premier écran : chiffres clés, panneau Neurone avec liens et poids, « Une nuit du cerveau » en 4 phases, Simuler une nuit / Rotation / Vue d'ensemble), **Cockpit** (ordre du moment, garde d'écriture avec vrais boutons, 4 voies avec leur activité, aperçu 2D, idée du jour, journal **en direct**), **Notes**, **Journal**. Menu à gauche sur Mac, onglets en bas sur iPhone, graphe en haut et panneaux dessous. |
| 8 · Démo | `exemples/demo.py` déroule tout d'un coup, sans clé ni réseau : 2 projets, notes liées et validées, une nuit, au moins une proposition par voie, une validation par la vraie commande, une lecture par client MCP, puis l'interface. |
| 9 · Documentation | `LISEZ-MOI.md` complet (démo pas à pas pour débutant, commandes, réglages, maquettes) et ce rapport. |

Corrections faites en route (des défauts réels, trouvés par les tests) :
- un test « le noyau ne cite aucun module » donnait un faux positif sur le mot MCP
  `notifications/initialized` : il vérifie désormais une vraie dépendance ;
- l'environnement n'était pas entièrement remis à zéro entre deux tests (fuite de `mode_ia`) :
  chaque test restaure maintenant tout l'environnement ;
- sur iPhone, le cockpit débordait en largeur à cause du tableau du journal.

## 3. Résultats des tests

**184 tests, tous réussis**, avec Python 3.13 et avec Python 3.9 (la version souvent installée
d'office sur Mac). Tous tournent dans un dossier temporaire, jamais dans le vrai `~/.jarvis`.

| Fichier de tests | Ce qu'il vérifie |
|---|---|
| `test_projets`, `test_synapses`, `test_recherche` | mémoire, étanchéité, synapses, recherche FTS5 |
| `test_corps_calleux`, `test_client_mcp` | les 4 messages, le serveur MCP, le vrai client |
| `test_routeur`, `test_routeur_ia`, `test_connecteurs`, `test_modeles` | routeur, budget, Gemini et Claude (faux serveurs), Ollama (faux serveur), notes sensibles |
| `test_orchestrateur`, `test_voies`, `test_garde_fous`, `test_valider` | hémisphère actif, 4 voies, garde-fous, validation humaine |
| `test_modules` | prise standard, notifications en console, retrait sans toucher au noyau |
| `test_sommeil*`, `test_reve`, `test_reglages` | sommeil, rêve, apprentissage, règles, réglages, démo |
| `interface/test_interface` | serveur web, accès protégé, données du cerveau, Simuler une nuit, journal en direct, contrat de design |

L'interface a aussi été ouverte dans un vrai navigateur (Chromium) sur ordinateur et sur iPhone :
aucune erreur, la 3D et les polices se chargent, aucun débordement de page.

## 4. Limites connues et ce qui n'est PAS testé pour de vrai

- **Ollama n'a jamais été lancé réellement** : seulement un faux serveur qui imite le vrai.
- **Gemini et Claude n'ont jamais été appelés réellement** (pas de clé ici) : faux serveurs
  seulement. Le nom du modèle Gemini (`gemini-2.5-flash`) n'est pas vérifié auprès de Google.
  Le prix de Claude, en dollars, est compté tel quel en euros (prudent).
- **Claude Desktop n'a pas été branché pour de vrai** au serveur MCP (testé avec le client minimal).
- **La tâche planifiée du Mac** (launchd, au réveil) n'a pas tourné sur un vrai Mac.
- **Sans Internet**, le cerveau 3D (Three.js) et les polices ne se chargent pas : l'aperçu 2D le
  remplace. Tout le reste fonctionne hors ligne.
- **L'interface n'est ouverte qu'au Mac lui-même** (127.0.0.1) : pas encore d'accès depuis l'iPhone
  (prévu avec le serveur, marche 8). La version iPhone se voit en rétrécissant la fenêtre.
- L'IA simulée donne des réponses simples, fabriquées à partir de modèles de phrases.
- La recherche FTS5 compte les mots de 3 lettres ou plus seulement.

## 5. Choix faits seul (non tranchés dans la consigne)

- **Continuer sur `prototype-1`** (déjà la branche la plus avancée) au lieu de la recréer.
- **Serveur MCP en Python standard**, sans le paquet `mcp` (permis mais pas nécessaire : rien à installer).
- **Noms courts en plus des noms existants** : `noyau/routeur.py` et `noyau/agents.py` renvoient à
  `routeur_ia.py` et `agent.py`, déjà testés, au lieu de tout renommer.
- **Les 4 voies proposent** sur des événements simples, choisis par moi : projet sans tâche,
  idée rêvée gardée, notes très proches (ressemblance ≥ 0,5), liens cassés. Les paires de notes
  sensibles ne sont pas comparées.
- **Garder une idée rêvée** crée un lien entre ses notes sources (seulement si elles sont validées)
  avant de le renforcer, sinon `activer` n'aurait rien à renforcer.
- **« Simuler une nuit »** est réservé aux projets de démo, pour ne jamais vieillir la vraie mémoire.
- **La démo** range ses données dans `~/.jarvis/demo/`, à part des vrais projets.
- **Couleurs** : les maquettes du cerveau utilisaient du violet et du bleu ; j'ai gardé la palette
  de la consigne (cyan et blanc), avec la disposition des maquettes.
- **Quatre écrans** (Cerveau 3D, Cockpit, Notes, Journal) au lieu de deux, comme dans la maquette
  du cockpit ; le premier écran est le cerveau 3D.

## 6. Décisions qui reviennent à Kayd

1. **Pousser `prototype-1` sur GitHub et ouvrir une pull request vers `main`** (la PR n°4 avec la
   marche 6 est toujours ouverte ; `prototype-1` la contient, elle pourra être fermée ou fusionnée avant).
2. **Passer aux vraies IA** : écrire toi-même tes clés dans `~/.jarvis/reglages.local`
   (`mode_ia=reel`, `CLE_API_GEMINI`, `CLE_API_ANTHROPIC`), jamais dans le chat.
3. **Installer Ollama** et renseigner `modele_local`, selon la mémoire de ton Mac (question ouverte n°1).
4. **Tes contraintes** pour noter les idées du rêve : `contrainte_budget_eur`, `contrainte_objectifs`.
5. **Brancher Claude Desktop** au cerveau (`python3 jarvis.py config-claude`).
6. **Tes deux premiers vrais projets**, et lesquels sont sensibles.
