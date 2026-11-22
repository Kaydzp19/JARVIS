# JARVIS

JARVIS est un assistant personnel modulaire, pensé comme un second cerveau.
Il repose sur un **noyau** générique (le moteur commun) auquel on branche des **modules** (une fonction précise chacun).
Le noyau ne contient rien de spécifique à un domaine : tout ce qui est particulier va dans un module.

> **État : prototype fonctionnel.** Toutes les briques tournent en version simple, avec une IA de
> démonstration (gratuite, locale, sans clé). Python seul : **rien à installer**.

## Comment c'est construit

```
INTERFACE        cockpit web local · éditeur de notes · cerveau 3D
HÉMISPHÈRE ACTIF                         HÉMISPHÈRE PASSIF
 orchestrateur (observer, décider,        notes Markdown = neurones
   agir, mesurer)                         synapses (liens pondérés)
 agents en 4 voies                        base SQLite par projet
 routeur IA (plafond 5 €/mois)            journal
 garde d'écriture · modules               sommeil (oubli + synthèse)
            \                                  /
             ===== CORPS CALLEUX (MCP) =====
              se_souvenir · proposer · activer · journal
```

- **Projets étanches** : un projet = un dossier = ses notes, sa base, son journal. Aucun accès entre projets.
- **Synapses** : chaque lien `[[Titre]]` relie deux notes. Le lien se renforce quand les notes servent
  ensemble, et s'affaiblit chaque nuit (oubli). Seules les notes validées renforcent des liens.
- **Garde d'écriture** : un agent ne fait que **proposer**. Rien n'est écrit avant ta validation.
  Aucun agent ne peut publier, payer ou supprimer.

## Démarrage rapide (Mac)

Ouvre l'application **Terminal**, va dans le dossier du dépôt, puis :

1. Créer les projets de démonstration (Demo-A normal, Demo-B sensible, fausses données) :
   `python3 jarvis.py demo`
2. Ouvrir le cockpit (il s'ouvre dans ton navigateur ; Ctrl + C pour l'arrêter) :
   `python3 jarvis.py cockpit`
3. Brancher Claude Desktop au cerveau : `python3 jarvis.py config-claude` affiche le réglage
   à coller, puis redémarre Claude Desktop et demande : « Que sais-tu du projet Demo-A ? »
4. Faire tourner le sommeil chaque nuit à 3 h 30 (si le Mac est allumé) :
   `python3 jarvis.py installer-sommeil`

Autres commandes : `python3 jarvis.py --help`. Pour essayer sans toucher à tes vraies données,
ajoute `--dossier /un/autre/dossier` juste après `jarvis.py`.

## Structure des dossiers

| Dossier | Rôle |
|---|---|
| `noyau/` | Le moteur commun : projets, synapses, corps calleux, serveur MCP, routeur IA, orchestrateur, agents, sommeil, prises pour modules. |
| `noyau/agents/` | Un fichier par agent : sa consigne et les seuls outils autorisés. |
| `modules/` | Les modules branchables. Exemple : `notifications` (mode DÉMO). Retirer un dossier retire le module. |
| `interface/` | Le cockpit web (serveur local + page avec le cerveau 3D). |
| `exemples/` | Les projets de démonstration. |
| `jarvis.py` | La commande principale (la « télécommande »). |

Fichiers à la racine : `.gitignore` (ce que Git ne doit jamais envoyer), `reglages.exemple`
(modèle de réglages sans aucune vraie valeur).

Tes données vont dans `~/.jarvis/` (jamais dans le dépôt) :
`projets/<nom>/notes/*.md`, `projets/<nom>/projet.db`, `systeme.db` (budget IA, modules).

## Tests

`python3 jarvis.py tests` lance tous les tests. Ils travaillent dans un dossier temporaire
et ne touchent jamais à `~/.jarvis`.

## Règle d'or : aucun secret dans ce dépôt

Ce dépôt est **public**. Aucune clé API, aucun mot de passe, aucun jeton ne doit y être écrit.

Pour configurer JARVIS :

1. Copier `reglages.exemple` en `reglages.local`.
2. Mettre ses vraies valeurs dans `reglages.local`.
3. `reglages.local` est bloqué par `.gitignore` : il reste uniquement sur votre ordinateur.

Les notes **sensibles** (ou d'un projet sensible) ne partent jamais vers une IA gratuite en ligne,
et leur texte est masqué quand Claude interroge le cerveau via MCP.
