// Tests de la planification côté interface : récurrence, validation, source de démo.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as PL from '../js/planification.js';
import { creerSourceDemo } from '../js/donnees_demo.js';
import { valider } from '../js/widgets/contrat.js';
import scene from '../js/widgets/scenes/planification.js';

const premieres = (ancre, rec, n = 4) => { const r = []; for (const d of PL.suite(ancre, rec)) { r.push(d); if (r.length >= n) break; } return r; };

test('récurrences (mêmes résultats que noyau/planification.py)', () => {
  assert.deepEqual(premieres('2027-01-01', 'jours_ouvres'), ['2027-01-01', '2027-01-04', '2027-01-05', '2027-01-06']);
  assert.deepEqual(premieres('2027-01-31', 'mensuelle'), ['2027-01-31', '2027-02-28', '2027-03-31', '2027-04-30']);
  assert.equal(PL.prochaineDate('2027-02-28', 'mensuelle', '2027-01-31'), '2027-03-31');
  const t = { echeance: '2027-01-02', recurrence: 'jours_ouvres', ancre: '2027-01-02' };
  assert.deepEqual(PL.occurrences(t, '2027-01-01', '2027-01-05'), ['2027-01-02', '2027-01-04', '2027-01-05']);
  assert.equal(PL.lundi('2027-01-06'), '2027-01-04');
});

test('validation des champs', () => {
  for (const m of [{ titre: '' }, { titre: 'x', heure: '25:00' }, { titre: 'x', duree: 2 }, { titre: 'x', recurrence: 'quotidienne' }, { titre: 'x', autre: 1 }]) {
    assert.throws(() => PL.validerChamps(m), JSON.stringify(m));
  }
  assert.deepEqual(PL.validerChamps({ titre: ' A ', date: '2027-01-04', recurrence: 'hebdomadaire' }),
    { titre: 'A', echeance: '2027-01-04', duree: 30, priorite: 'normale', recurrence: 'hebdomadaire' });
});

test('démo : créer, modifier, terminer, supprimer ; lecture seule pour « tous »', async () => {
  const s = creerSourceDemo({ aujourdhui: '2027-01-04' });
  const { id } = await s.taches('creer', 'Projet A', { champs: { titre: 'Essai', date: '2027-01-05', heure: '10:00' } });
  await s.taches('modifier', 'Projet A', { id, champs: { heure: '11:15', date: '2027-01-06' } });
  let ev = await s.ouvrirPlanification('Projet A', '2027-01-04', 'semaine');
  assert.deepEqual(valider(ev), []);
  const t = ev.donnees.taches.find((x) => x.id === id);
  assert.equal(t.date + ' ' + t.heure, '2027-01-06 11:15');
  assert.equal((await s.taches('terminer', 'Projet A', { id, fait: true })).statut, 'fait');
  await s.taches('supprimer', 'Projet A', { id });
  ev = await s.ouvrirPlanification('Projet A', '2027-01-04', 'semaine');
  assert.ok(!ev.donnees.taches.some((x) => x.id === id));
  await assert.rejects(s.taches('creer', '*', { champs: { titre: 'x' } }));
  const journal = (await s.journalDuJour()).map((l) => l.evenement).join(' | ');
  for (const mot of ['créée : Essai', 'modifiée', 'fait', 'supprimée : Essai']) assert.ok(journal.includes(mot), mot);
});

test('démo : navigation, filtre projet, agenda en lecture seule', async () => {
  const s = creerSourceDemo({ aujourdhui: '2027-01-04' });
  const ev = await s.ouvrirPlanification('Projet A', '2027-01-04', 'semaine');
  assert.ok(ev.donnees.externes.disponible && !ev.donnees.externes.modifiable);
  const suivant = await s.action(ev.id, 'suivant', {});
  assert.equal(suivant.affichage.donnees.debut, '2027-01-11');
  const tous = await s.action(ev.id, 'filtre', { projet: 'tous' });
  assert.equal(tous.affichage.donnees.lecture_seule, true);
  const jour = await s.action(ev.id, 'onglet', { vue: 'jour' });
  assert.equal(jour.affichage.donnees.jours, 1);
  assert.equal((await s.prochaines(3)).length, 3);
  const r = await s.demander('Mes tâches de demain', 'Projet A');
  assert.equal(r.affichage.scene, 'planification');
  assert.equal(r.affichage.donnees.vue, 'jour');
});

test('scène : déposer une tâche donne une date et une heure au quart d’heure', () => {
  const g = { x0: 100, x1: 400, lignes: [{ date: '2027-01-04', y: 0, h: 50 }, { date: '2027-01-05', y: 52, h: 50 }] };
  const z = { tache: { date: '2027-01-04', heure: '09:00', duree: 30 } };
  const ev = { donnees: { lecture_seule: false } };
  // 300 px pour 15 h : x = 250 -> 14 h 30, moins la moitié de la durée -> 14 h 15
  assert.deepEqual(scene.deposer(z, 250, 70, ev, {}, g), { date: '2027-01-05', heure: '14:15' });
  assert.equal(scene.deposer(z, 250, 70, { donnees: { lecture_seule: true } }, {}, g), null);
});
