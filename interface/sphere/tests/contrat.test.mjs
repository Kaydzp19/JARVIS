// Tests du contrat d'affichage côté interface (même règles que noyau/affichage.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { estEcriture, normaliser, valider } from '../js/widgets/contrat.js';

const ev = (x = {}) => ({ scene: 'graphique', titre: 'Dépenses IA', donnees: { serie: [1, 2] }, ...x });

test('événement minimal valide, scène inconnue acceptée', () => {
  assert.deepEqual(valider(ev()), []);
  assert.deepEqual(valider(ev({ scene: 'carte_du_monde' })), []);
});

test('erreurs de forme', () => {
  for (const mauvais of ['texte', ev({ scene: 'Avec Espace' }), ev({ titre: '' }), ev({ titre: 'x'.repeat(121) }),
    ev({ donnees: [1] }), ev({ inconnu: 1 }), ev({ fermeture: -1 }), ev({ controles: { periode: ['1 siècle'] } }),
    ev({ controles: { zoom: ['x'] } }), ev({ controles: { tri: [] } }),
    ev({ actions: [{ id: 'a', libelle: 'x' }, { id: 'a', libelle: 'y' }] }), ev({ actions: [{ id: 'a', libelle: 'x', type: 'magie' }] })]) {
    assert.ok(valider(mauvais).length, JSON.stringify(mauvais));
  }
});

test('jamais de texte de note', () => {
  for (const cle of ['contenu', 'texte', 'extrait', 'Contenu']) {
    const e = valider(ev({ donnees: { notes: [{ titre: 'x', [cle]: 'y' }] } }));
    assert.ok(e.length && e[0].includes('jamais'), cle);
  }
});

test('vue transversale en lecture seule et écritures reconnues', () => {
  assert.ok(valider(ev({ projet: '*', actions: [{ id: 'supprimer', libelle: 'Supprimer' }] })).length);
  for (const nom of ['supprimer', 'publier', 'payer', 'ecrire_note', 'envoyer']) assert.ok(estEcriture({ id: nom }), nom);
  assert.ok(!estEcriture({ id: 'periode' }));
  const n = normaliser(ev({ actions: [{ id: 'publier', libelle: 'Publier' }, { id: 'voir', libelle: 'Voir' }] }));
  assert.deepEqual(n.actions.map((a) => a.type), ['ecriture', 'lecture']);
});
