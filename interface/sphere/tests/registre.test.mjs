// Tests de l'application des événements d'affichage (sans dessin).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { creerRegistre, dureeAffichage, filtrer, trier } from '../js/widgets/registre.js';

const ev = (x = {}) => ({ id: 1, version: 1, scene: 'graphique', titre: 'Dépenses', donnees: { periode: '6 mois' }, ...x });

test('ouvrir, mettre à jour, ignorer une ancienne version, refuser', () => {
  const r = creerRegistre();
  assert.equal(r.appliquer(ev()).geste, 'ouvrir');
  const maj = r.appliquer(ev({ version: 2, donnees: { periode: '7 j' } }));
  assert.equal(maj.geste, 'mettre_a_jour');
  assert.equal(r.courant.donnees.periode, '7 j');
  assert.equal(r.appliquer(ev({ version: 2 })).geste, 'ignorer');
  assert.equal(r.appliquer(ev({ version: 1 })).geste, 'ignorer');
  const refus = r.appliquer({ scene: 'x', titre: 'x', donnees: { contenu: 'secret' } });
  assert.equal(refus.geste, 'refuser');
  assert.equal(r.courant.id, 1);                            // l'hologramme affiché ne change pas
  assert.equal(r.appliquer(ev({ id: 2 })).geste, 'ouvrir'); // un seul à la fois : il remplace
  assert.equal(r.fermer().id, 2);
  assert.equal(r.courant, null);
});

test('scène inconnue : widget générique, jamais d’erreur', () => {
  const r = creerRegistre().appliquer(ev({ scene: 'carte_projets' }));
  assert.equal(r.geste, 'ouvrir');
  assert.equal(r.generique, true);
});

test('durée, tri et filtre locaux', () => {
  assert.equal(dureeAffichage(ev({ fermeture: 0 })), 0);
  assert.ok(dureeAffichage(ev()) > 10);
  const l = [{ titre: 'Été', score: 0.2, rang: 2 }, { titre: 'avion', score: 0.9, rang: 1 }];
  assert.deepEqual(trier(l, 'score').map((x) => x.titre), ['avion', 'Été']);
  assert.deepEqual(trier(l, 'titre').map((x) => x.titre), ['avion', 'Été']);
  assert.deepEqual(trier(l, 'rang').map((x) => x.rang), [1, 2]);
  assert.deepEqual(filtrer(l, 'ete').map((x) => x.titre), ['Été']);
  assert.equal(filtrer(l, '').length, 2);
});
