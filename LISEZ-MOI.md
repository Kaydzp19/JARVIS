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
4. Lancer le rêve à chaque réveil du Mac (au plus une fois par 24 h) :
   `python3 jarvis.py installer-sommeil`

Autres commandes : `python3 jarvis.py --help`. Pour essayer sans toucher à tes vraies données,
ajoute `--dossier /un/autre/dossier` juste après `jarvis.py`.

## Sommeil et rêve

`python3 jarvis.py dormir` (tous les projets) ou `python3 jarvis.py dormir Demo-A` (un seul).
Règle des 24 h : un projet qui a déjà rêvé dans les dernières 24 heures est laissé tranquille.
C'est une commande autonome : aujourd'hui, `python3 jarvis.py installer-sommeil` la fait lancer
par le Mac à chaque réveil et à l'ouverture de session ; demain, un mode nuit ou un serveur
pourra l'appeler de la même façon. Rien ne touche à la veille du Mac.

Chaque projet rêve seul (étanchéité conservée), en 4 phases, chacune notée au journal :

| Phase | Ce qui se passe |
|---|---|
| Tri | Le code applique l'oubli et archive les liens trop faibles. Puis l'IA repère doublons, notes orphelines et notes périmées : chaque correction devient une **proposition** à valider. |
| Analyse | Résumé du projet entier (code puis IA, au plus `tokens_max_analyse` jetons envoyés) et synthèses proposées pour les groupes de notes très liées. |
| Rêve | Des paires ou triplets de notes **éloignées** sont tirés au hasard ; une IA créative (température haute) imagine `candidates_par_nuit` idées. |
| Réveil | Une IA rigoureuse note chaque idée (nouveauté, utilité, faisabilité selon tes contraintes) et ne garde que **la meilleure** (`idees_par_projet`, 1 par défaut). |

L'idée du jour : `python3 jarvis.py reve`. Ta décision :
`python3 jarvis.py reve garder Demo-A:1 "raison"` ou `python3 jarvis.py reve rejeter Demo-A:1 "raison"`.
Une idée gardée renforce les liens entre ses notes sources ; la raison d'un rejet est rappelée
au rêve suivant pour ne pas la répéter. Le rêve ne fait que proposer : il n'agit jamais.

**Quelle IA ?**
- Le modèle local (Ollama, gratuit, sur ton Mac) d'abord, s'il est installé et renseigné
  (`modele_local`). Lui seul peut recevoir des notes sensibles.
- Sans modèle local : les notes sensibles sont exclues du rêve ; les autres peuvent passer par
  l'offre gratuite autorisée par le routeur.
- Cloud payant : seulement pour la phase réveil, si `cloud_pour_reveil=true`, dans la limite
  du budget IA mensuel du routeur. Jamais de note sensible vers une offre gratuite.

**Réglages** : `~/.jarvis/reglages.local` (hors du dépôt), créé tout seul avec les valeurs par
défaut à la première commande. Tu y mets aussi tes contraintes : `contrainte_budget_eur`,
`contrainte_niveau`, `contrainte_objectifs`.

Sans clé API ni Ollama, tout tourne en mode démo (IA de démonstration, 0 €) :
`python3 jarvis.py demo`, puis `python3 jarvis.py reve`.

## Structure des dossiers

| Dossier | Rôle |
|---|---|
| `noyau/` | Le moteur commun : projets, synapses, corps calleux, serveur MCP, routeur IA, orchestrateur, agents, sommeil et rêve, prises pour modules. |
| `noyau/agents/` | Un fichier par agent : sa consigne et les seuls outils autorisés. |
| `modules/` | Les modules branchables. Exemple : `notifications` (mode DÉMO). Retirer un dossier retire le module. |
| `interface/` | Le cockpit web (serveur local + page avec le cerveau 3D). |
| `exemples/` | Les projets de démonstration. |
| `jarvis.py` | La commande principale (la « télécommande »). |

Fichiers à la racine : `.gitignore` (ce que Git ne doit jamais envoyer), `reglages.exemple`
(modèle de réglages sans aucune vraie valeur ; les vrais réglages vivent dans `~/.jarvis/reglages.local`).

Tes données vont dans `~/.jarvis/` (jamais dans le dépôt) :
`projets/<nom>/notes/*.md`, `projets/<nom>/projet.db`, `systeme.db` (budget IA, modules).

## Tests

`python3 jarvis.py tests` lance tous les tests. Ils travaillent dans un dossier temporaire
et ne touchent jamais à `~/.jarvis`.

## Règle d'or : aucun secret dans ce dépôt

Ce dépôt est **public**. Aucune clé API, aucun mot de passe, aucun jeton ne doit y être écrit.

Pour configurer JARVIS : ouvre `~/.jarvis/reglages.local` (créé automatiquement à la première
commande) et mets-y tes vraies valeurs. Ce fichier est dans ton dossier personnel, hors du dépôt :
il n'est jamais envoyé sur GitHub. `reglages.exemple` montre les réglages possibles.

Les notes **sensibles** (ou d'un projet sensible) ne partent jamais vers une IA gratuite en ligne,
et leur texte est masqué quand Claude interroge le cerveau via MCP.
