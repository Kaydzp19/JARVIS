// Tests de la source unique d'intensité de parole.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { creerParole } from '../js/parole.js';

function horloge() {
  let t = 0; const file = [];
  return { maintenant: () => t, image: (f) => file.push(f), avancer(ms) { t += ms; const f = file.splice(0); f.forEach((x) => x()); return f.length; } };
}

test('une impulsion monte l’intensité, qui redescend seule jusqu’à zéro', () => {
  const h = horloge(), p = creerParole(h);
  const vus = [];
  p.abonner((e) => vus.push(e.type));
  p.debut('Projet A');
  p.impulsion(0.8);
  assert.equal(p.valeur, 0.8);
  assert.equal(p.origine, 'Projet A');
  let n = 0;
  while (p.valeur > 0 && n++ < 500) h.avancer(50);
  assert.equal(p.valeur, 0);
  assert.equal(h.avancer(50), 0);                 // plus rien ne tourne au repos
  assert.ok(vus.includes('debut') && vus.includes('impulsion') && vus.includes('niveau'));
});

test('force selon le mot ; rien pour la ponctuation seule', () => {
  const p = creerParole(horloge());
  assert.equal(p.forceMot('…'), 0);
  assert.equal(p.forceMot(','), 0);
  assert.ok(p.forceMot('anticonstitutionnellement') > p.forceMot('le'));
  assert.ok(p.forceMot('le') > 0);
  p.impulsion(5);
  assert.equal(p.valeur, 1);                       // bornée entre 0 et 1
});

test('fin de réponse : parle redevient faux', () => {
  const p = creerParole(horloge());
  p.debut(); assert.equal(p.parle, true);
  p.fin(); assert.equal(p.parle, false);
});
