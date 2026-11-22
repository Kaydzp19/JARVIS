"""
Garde-fous de JARVIS : aucune écriture, publication, paiement ou suppression
sans validation humaine explicite (python3 -m noyau.valider <id>).
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from noyau import agents
from noyau import corps_calleux as cc
from noyau import orchestrateur, projets, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire

RACINE_DEPOT = Path(__file__).resolve().parent.parent


class TestGardeFous(TestTemporaire):

    def empreinte(self):
        """Tout ce qui est écrit dans la mémoire : fichiers des notes + table notes."""
        h = hashlib.sha256()
        for p in projets.lister_projets(racine=self.racine):
            for n in projets.lister_notes(p, racine=self.racine):
                h.update(json.dumps(n, sort_keys=True).encode())
                h.update(projets.lire_note(p, n["id"], racine=self.racine).encode())
            h.update(json.dumps(projets.lister_taches(p, racine=self.racine), sort_keys=True).encode())
        return h.hexdigest()

    def test_aucun_outil_d_agent_ne_peut_ecrire_publier_payer_supprimer(self):
        self.assertEqual(set(agents.OUTILS_PERMIS),
                         {"se_souvenir", "proposer", "activer", "journal", "ia"})
        for nom, a in agents.charger_tous(racine=self.racine).items():
            self.assertTrue(set(a.outils) <= set(agents.OUTILS_PERMIS), nom)
            for interdit in ("ecrire", "valider", "supprimer", "publier", "payer",
                             "modifier_note", "creer_note"):
                self.assertFalse(hasattr(a, interdit), f"{nom}.{interdit}")
        with self.assertRaises(ValueError):
            agents.Agent("pirate", "proposer", "x", ["proposer", "supprimer"])

    def test_actions_dangereuses_refusees_meme_en_proposition(self):
        projets.creer_projet("A", racine=self.racine)
        for t in ("publication", "paiement", "suppression", "envoi", "achat"):
            with self.assertRaises(ValueError):
                cc.proposer("A", t, "à faire tout de suite", racine=self.racine)

    def test_rien_n_est_ecrit_sans_validation_puis_ecriture_et_journal(self):
        projets.creer_projet("A", racine=self.racine)
        n = lambda t, x: cc.creer_note_humaine("A", t, x, date=JOUR_1, racine=self.racine)
        n("Prix", "Le prix de base est de 490 euros par page.")
        n("Tarifs", "Le prix de base est de 490 euros la page.")
        n("Plan", "Voir [[Fantôme]].")
        n("Course", "Courir trois fois par semaine.")
        avant = self.empreinte()
        # Toute la machine tourne : orchestrateur (4 voies), sommeil et rêve.
        orchestrateur.tour(JOUR_1, racine=self.racine)
        sommeil.dormir(JOUR_1, projet="A", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        en_attente = cc.lister_propositions("A", "en attente", racine=self.racine)
        self.assertGreaterEqual(len(en_attente), 3)
        self.assertEqual(self.empreinte(), avant)  # RIEN n'a été écrit

        # Seule la commande humaine écrit, et le journal le note.
        pid = en_attente[0]["id"]
        r = subprocess.run([sys.executable, "-m", "noyau.valider", f"A:{pid}"],
                           cwd=str(RACINE_DEPOT), env=dict(os.environ), capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.empreinte(), avant)
        derniere = [l for l in projets.lire_journal("A", racine=self.racine)
                    if l["evenement"] == f"proposition {pid} validée"]
        self.assertEqual(derniere[0]["acteur"], "kayd")

    def test_le_noyau_ne_supprime_jamais_une_note(self):
        for f in (RACINE_DEPOT / "noyau").glob("*.py"):
            if f.name.startswith("test_"):
                continue
            texte = f.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"DELETE\s+FROM\s+notes\b(?!_fts)", texte), f.name)
            for geste in (".unlink(", "rmtree(", "os.remove("):
                self.assertNotIn(geste, texte, f"{f.name} : {geste}")
