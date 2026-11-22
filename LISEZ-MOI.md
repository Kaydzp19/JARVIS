# JARVIS

JARVIS est un assistant personnel modulaire.
Il repose sur un **noyau** générique (le moteur commun) auquel on branche des **modules** (une fonction précise chacun).
Le noyau ne contient rien de spécifique à un domaine : tout ce qui est particulier va dans un module.

## Structure des dossiers

| Dossier       | Rôle |
|---------------|------|
| `noyau/`      | Le moteur commun de JARVIS, générique. |
| `modules/`    | Les fonctions ajoutées au noyau, une par module. |
| `interface/`  | Ce que l'utilisateur voit et utilise pour parler à JARVIS. |
| `exemples/`   | Des exemples d'utilisation et de configuration. |

Fichiers à la racine :

- `LISEZ-MOI.md` : ce fichier.
- `.gitignore` : la liste des fichiers que Git ne doit jamais envoyer sur GitHub.
- `reglages.exemple` : un modèle de réglages, sans aucune vraie valeur.

## Règle d'or : aucun secret dans ce dépôt

Ce dépôt est **public**. Aucune clé API, aucun mot de passe, aucun jeton ne doit y être écrit.

Pour configurer JARVIS :

1. Copier `reglages.exemple` en `reglages.local`.
2. Mettre ses vraies valeurs dans `reglages.local`.
3. `reglages.local` est bloqué par `.gitignore` : il reste uniquement sur votre ordinateur.

Les données personnelles (dossier `~/.jarvis`, bases de données) ne vont jamais dans le dépôt non plus.
