"""
Petits outils partagés par tout le noyau (dates, texte).
Uniquement la bibliothèque standard de Python.
"""

import re
import unicodedata
from datetime import date as _date, datetime


def jour(d=None):
    """
    Renvoie une date (sans l'heure).
    - d absent : la date du jour (seul endroit où l'horloge est lue) ;
    - d date Python ou texte 'AAAA-MM-JJ...' : converti.
    Toutes les fonctions acceptent une date en paramètre : les tests
    peuvent ainsi simuler n'importe quel jour.
    """
    if d is None:
        return _date.today()
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, _date):
        return d
    return _date.fromisoformat(str(d)[:10])


def normaliser(texte):
    """Minuscules et sans accents, pour comparer des mots simplement."""
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


# Petits mots ignorés dans les recherches.
MOTS_VIDES = set(normaliser(
    "les des une un le la de du et ou en au aux sur pour par avec dans que qui "
    "quoi est sont sais tu je il elle nous vous ils ce cette ces mon ma mes ton "
    "ta tes son sa ses leur leurs pas plus moins tout tous fait faire"
).split())


def mots_cles(texte):
    """Découpe un texte en mots utiles (3 lettres ou plus, sans mots vides)."""
    mots = re.findall(r"\w+", normaliser(texte))
    return [m for m in mots if len(m) >= 3 and m not in MOTS_VIDES]
