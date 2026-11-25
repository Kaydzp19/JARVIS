// Tests de la source de démonstration (fausses données, dans le navigateur).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { creerSourceDemo, genererMemoire, router, tracer } from '../js/donnees_demo.js';
import { valider } from '../js/widgets/contrat.js';
import { comparerNuit } from '../js/donnees.js';

test('220 neurones (96, 72, 52), environ 320 synapses, aucune entre projets', () => {
  const p = genererMemoire();
  assert.deepEqual(p.map((x) => x.neurones.length), [96, 72, 52]);
  const total = p.reduce((s, x) => s + x.synapses.length, 0);
  assert.ok(total > 270 && total < 380, `synapses : ${total}`);
  p.forEach((x) => {
    const ids = new Set(x.neurones.map((n) => n.id));
    x.synapses.forEach((s) => assert.ok(ids.has(s.a) && ids.has(s.b)));
  });
  assert.deepEqual(genererMemoire(), p);                    // reproductible
});

test('trace : 6 notes au plus, des identifiants et des scores, jamais de texte', () => {
  const p = genererMemoire()[0];
  const t = tracer(p, 'que sais-tu du budget ?', 6);
  assert.equal(t.retenues.length, 6);
  assert.equal(t.graines.length, 3);
  assert.equal(t.appel_ia, false);
  assert.ok(!/contenu|extrait|texte/.test(JSON.stringify(t)));
  assert.deepEqual(t.retenues.map((r) => r.rang), [1, 2, 3, 4, 5, 6]);
  const cles = new Set(p.synapses.map((s) => Math.min(s.a, s.b) + ':' + Math.max(s.a, s.b)));
  t.synapses.forEach((s) => assert.ok(cles.has(s.a + ':' + s.b)));
  assert.deepEqual(tracer(p, 'que sais-tu du budget ?', 6), t);
});

test('routage de la démo par mots-clés', () => {
  assert.equal(router('État de mon Mac'), 'machine');
  assert.equal(router('Simule une nuit'), 'nuit');
  assert.equal(router('Résumé de la nuit'), 'resume_nuit');
  assert.equal(router('Ouvre ma note sensible'), 'note_privee');
  assert.equal(router('Que sais-tu du projet A ?'), 'se_souvenir');
});

test('réponses de la démo : événements valides, rien à valider au démarrage', async () => {
  const s = creerSourceDemo();
  assert.deepEqual(await s.aValider(), []);
  for (const q of ['Que sais-tu du projet A ?', 'Où en sont mes projets ?', 'État de mon Mac', 'Météo',
    'Résumé de la nuit', 'Graphique de mes dépenses', 'Ouvre ma note sensible', 'Montre la carte']) {
    const r = await s.demander(q, 'Projet A');
    assert.equal(r.routeur, 'routeur : aucun appel IA');
    assert.deepEqual(valider(r.affichage), [], q);
  }
  const tous = await s.demander('Où en sont mes projets ?', 'Projet A');
  assert.equal(tous.recherche.traces.length, 3);
  tous.recherche.traces.forEach((t) => assert.ok(t.retenues.length <= 4));
  assert.ok(!tous.affichage.actions.some((a) => a.type === 'ecriture'));
});

test('garde d’écriture : une action d’écriture devient une proposition à valider', async () => {
  const s = creerSourceDemo();
  const r = await s.demander('Que sais-tu du projet A ?', 'Projet A');
  const a = await s.action(r.affichage.id, 'creer_synthese', {});
  assert.equal(a.type, 'a_valider');
  assert.equal((await s.aValider()).length, 1);
  const g = await s.demander('Graphique de mes dépenses', 'Projet A');
  const maj = await s.action(g.affichage.id, 'periode', { periode: '7 j' });
  assert.equal(maj.type, 'mise_a_jour');
  assert.equal(maj.affichage.version, 2);
  assert.equal(maj.affichage.donnees.serie.length, 7);
  await assert.rejects(s.action(g.affichage.id, 'lancer_fusee', {}));
});

test('nuit de démo : vraie règle (oubli 2 %, +0,10, archivage sous 0,05), une idée par projet', async () => {
  const s = creerSourceDemo();
  const avant = await s.sphere();
  const poids = new Map(avant.projets.flatMap((p) => p.synapses.map((x) => [p.nom + x.a + ':' + x.b, x.poids])));
  const b = await s.simulerNuit();
  assert.equal(b.propositions.length, 3);
  b.propositions.forEach((p) => assert.equal(p.notes.length, 2));
  b.archivees.forEach((x) => assert.ok(0.98 * poids.get(x.projet + x.a + ':' + x.b) < 0.05));
  const apres = await s.sphere();
  assert.equal(apres.compteurs.synapses, avant.compteurs.synapses - b.archivees.length);
  assert.equal((await s.aValider()).length, 3);
  const b2 = await s.simulerNuit();
  assert.equal(b2.propositions.length, 0);                 // déjà une idée en attente par projet
});

test('bilan de nuit réelle : comparaison avant / après', () => {
  const avant = { projets: [{ nom: 'A', synapses: [{ a: 1, b: 2, poids: 0.5 }, { a: 2, b: 3, poids: 0.051 }], propositions: [{ id: 1 }] }] };
  const apres = { projets: [{ nom: 'A', synapses: [{ a: 1, b: 2, poids: 0.59 }], propositions: [{ id: 1 }, { id: 4, titre: 'Idée', notes: [1, 3] }] }] };
  const b = comparerNuit(avant, apres, ['A']);
  assert.deepEqual(b.renforcees, [{ projet: 'A', a: 1, b: 2 }]);
  assert.deepEqual(b.archivees, [{ projet: 'A', a: 2, b: 3 }]);
  assert.equal(b.propositions[0].id, 4);
});
