// Test de bout en bout de l'interface « sphère » (Playwright + Chromium, WebGL logiciel).
// Lancé par interface/test_e2e_sphere.py (JARVIS_E2E=1), avec un serveur sur des données
// de démonstration dans un dossier temporaire. Écrit un bilan JSON sur la sortie standard.
//
//   node e2e_playwright.mjs <adresse de base> <jeton> [dossier des captures]

import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); } catch (e) {
  playwright = require(execSync('npm root -g').toString().trim() + '/playwright');
}
const [base, jeton, captures] = process.argv.slice(2);
const ARGS = ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
const bilan = { etapes: [], erreurs: [], captures: [] };
const ok = (nom, vrai, detail = '') => { bilan.etapes.push({ nom, ok: !!vrai, detail: String(detail).slice(0, 300) }); };

async function page(navigateur, { largeur = 1440, hauteur = 880, chemin = '/', options = {} } = {}) {
  const ctx = await navigateur.newContext({ viewport: { width: largeur, height: hauteur }, deviceScaleFactor: 1, ...options });
  const p = await ctx.newPage();
  p.on('console', (m) => { if (m.type() === 'error') bilan.erreurs.push(`${chemin} : ${m.text()}`); });
  p.on('pageerror', (e) => bilan.erreurs.push(`${chemin} : ${e.message}`));
  await p.goto(`${base}${chemin}${chemin.includes('?') ? '&' : '?'}jeton=${jeton}`);
  await p.waitForFunction(() => window.__JARVIS && window.__JARVIS.pret, null, { timeout: 45000 });
  return p;
}
const attendreLibre = (p) => p.waitForFunction(() => !window.__JARVIS.occupe, null, { timeout: 60000 });
const scene = (p) => p.evaluate(() => (window.__JARVIS.holo && window.__JARVIS.holo.courant ? window.__JARVIS.holo.courant.scene : null));
const capture = async (p, nom) => { if (captures) { const f = `${captures}/${nom}.png`; await p.screenshot({ path: f }); bilan.captures.push(f); } };

async function demander(p, texte, suivrePhases = false) {
  const phases = new Set();
  await p.fill('#question', texte);
  await p.press('#question', 'Enter');
  if (suivrePhases) {
    for (let i = 0; i < 60; i++) {
      const t = (await p.textContent('#phase')) || '';
      const m = /^(\d) · ([A-ZÉ]+)/.exec(t);
      if (m) phases.add(m[1] + ' ' + m[2]);
      if (m && m[1] === '3') {
        const n = await p.locator('.etq').count();
        if (n) phases.add('étiquettes:' + n);
      }
      await p.waitForTimeout(250);
      if (!(await p.evaluate(() => window.__JARVIS.occupe))) break;
    }
  }
  await attendreLibre(p);
  await p.waitForTimeout(700);
  return phases;
}

const nav = await playwright.chromium.launch({ args: ARGS });
try {
  // ---------- mode réel (données de démonstration créées par jarvis.py demo) ----------
  const p = await page(nav);
  ok('page réelle prête', await p.evaluate(() => window.__JARVIS.mode === 'reel'));
  ok('badge démo affiché (projets de démo)', await p.isVisible('#badge-demo'));
  ok('aucune erreur au démarrage', bilan.erreurs.length === 0, bilan.erreurs.join(' | '));
  const nbAvant = Number(await p.textContent('#nb-a-valider'));

  // Vague complète en 4 temps
  const phases = await demander(p, 'Que sais-tu des clients ?', true);
  const vues = [...phases].join(', ');
  ok('vague : 4 temps vus', ['1 NOTATION', '2 PROPAGATION', '3 SÉLECTION', '4 RÉPONSE'].every((x) => phases.has(x)), vues);
  ok('vague : titres numérotés affichés', [...phases].some((x) => x.startsWith('étiquettes:')), vues);
  ok('ligne d’outil brute', (await p.locator('#messages .m.t .tx').last().textContent()).includes('se_souvenir(projet="Projet A"'));
  ok('hologramme notes retenues', (await scene(p)) === 'notes_retenues');
  await capture(p, 'sphere-1440x880-notes-retenues');

  // Notes retenues : clic sur une note → neurone allumé ; tri ; filtre ; ouvrir la note
  const zone = p.locator('.holo .zone').first();
  await zone.click();
  ok('note cliquée : sélectionnée', (await zone.getAttribute('aria-pressed')) === 'true');
  ok('note cliquée : neurone allumé', await p.evaluate(() => window.__JARVIS.sphere.S.selection >= 0));
  await p.selectOption('.holo select', 'titre');
  ok('tri local', (await p.evaluate(() => window.__JARVIS.holo.ui.tri)) === 'titre');
  await p.fill('.holo input[type=search]', 'zzz-introuvable');
  ok('filtre local', (await p.locator('.holo .zone').count()) === 0);
  await p.fill('.holo input[type=search]', '');
  const premiere = p.locator('.holo .zone').first();           // recliquer une note la désélectionne
  if ((await premiere.getAttribute('aria-pressed')) !== 'true') await premiere.click();
  await p.click('.holo button[data-action="ouvrir_note"]');
  await p.waitForTimeout(400);
  ok('ouvrir la note : éditeur local', await p.evaluate(() => document.getElementById('editeur').open));
  await p.click('#editeur-fermer');

  // Garde d'écriture : l'action d'écriture devient une proposition à valider
  await p.click('.holo button[data-action="creer_synthese"]');
  await p.waitForFunction((n) => Number(document.getElementById('nb-a-valider').textContent) === n + 1, nbAvant, { timeout: 10000 }).catch(() => {});
  ok('écriture depuis un widget → « À valider »', Number(await p.textContent('#nb-a-valider')) === nbAvant + 1);

  // Graphique : période (affichage.action → mise à jour sur place) et infobulle
  await demander(p, 'Graphique de mes dépenses');
  ok('hologramme graphique', (await scene(p)) === 'graphique');
  const id = await p.evaluate(() => window.__JARVIS.holo.courant.id);
  await p.click('.holo .controles button:has-text("7 j")');
  await p.waitForFunction(() => window.__JARVIS.holo.courant && window.__JARVIS.holo.courant.version === 2, null, { timeout: 10000 }).catch(() => {});
  const apres = await p.evaluate(() => window.__JARVIS.holo.courant);
  ok('période : mise à jour sur place', apres && apres.id === id && apres.version === 2 && apres.donnees.serie.length === 7);
  await p.locator('.holo .zone').nth(3).hover();
  ok('infobulle sur une barre', await p.isVisible('.holo .info'));

  // Machine : objet 3D tourné, épingler, déplacer, redimensionner, Échap
  await demander(p, 'État de ma machine');
  ok('hologramme machine', (await scene(p)) === 'machine');
  const h = await p.locator('.holo .heros').boundingBox();
  if (h) { await p.mouse.move(h.x + h.width / 2, h.y + h.height / 2); await p.mouse.down(); await p.mouse.move(h.x + h.width / 2 + 60, h.y + h.height / 2, { steps: 5 }); await p.mouse.up(); }
  const rot = await p.evaluate(() => window.__JARVIS.holo.heros);
  ok('objet 3D tourné à la main', rot && Math.abs(rot.y) > 0.2, JSON.stringify(rot));
  await p.click('.holo .outils button[aria-pressed]');
  ok('épingler', (await p.getAttribute('.holo .outils button[aria-pressed]', 'aria-pressed')) === 'true');
  const b0 = await p.locator('.holo').boundingBox();
  const g = await p.locator('.holo .poignee').boundingBox();
  await p.mouse.move(g.x + 40, g.y + 15); await p.mouse.down(); await p.mouse.move(g.x + 10, g.y - 25, { steps: 6 }); await p.mouse.up();
  const b1 = await p.locator('.holo').boundingBox();
  ok('déplacer', Math.abs(b1.y - b0.y) > 10 || Math.abs(b1.x - b0.x) > 10, `${b0.x},${b0.y} → ${b1.x},${b1.y}`);
  const r = await p.locator('.holo .redim').boundingBox();
  await p.mouse.move(r.x + 9, r.y + 9); await p.mouse.down(); await p.mouse.move(r.x - 70, r.y - 30, { steps: 6 }); await p.mouse.up();
  const b2 = await p.locator('.holo').boundingBox();
  ok('redimensionner', b2.width < b1.width - 30, `${b1.width} → ${b2.width}`);
  await capture(p, 'sphere-1440x880-machine');
  await p.keyboard.press('Escape');
  await p.waitForTimeout(600);
  ok('Échap ferme l’hologramme', (await scene(p)) === null);

  await demander(p, 'Résumé de la nuit');
  ok('hologramme résumé de la nuit', (await scene(p)) === 'resume_nuit');
  await demander(p, 'Météo');
  ok('hologramme météo (indisponible sans position)', (await scene(p)) === 'meteo');
  await p.click('.holo .outils button:has-text("×")');
  await p.waitForTimeout(500);
  ok('× ferme l’hologramme', (await scene(p)) === null);

  // Valider une proposition depuis « À valider »
  const n0 = Number(await p.textContent('#nb-a-valider'));
  await p.locator('#a-valider button.ok').first().click();
  await p.waitForFunction((n) => Number(document.getElementById('nb-a-valider').textContent) === n - 1, n0, { timeout: 10000 }).catch(() => {});
  ok('Valider (garde d’écriture)', Number(await p.textContent('#nb-a-valider')) === n0 - 1);

  // ---------- impulsions pendant une réponse, puis plus aucun redessin au repos ----------
  await p.evaluate(() => { window.__imp = 0; window.__vuesImp = 0; window.__JARVIS.parole.abonner((e) => { if (e.type === 'impulsion') window.__imp++; }); });
  await p.fill('#question', 'Résumé de la nuit');
  await p.press('#question', 'Enter');
  for (let i = 0; i < 80; i++) {
    await p.waitForTimeout(150);
    if (await p.evaluate(() => window.__JARVIS.sphere.S.impulsions.length > 0)) await p.evaluate(() => { window.__vuesImp++; });
    if (!(await p.evaluate(() => window.__JARVIS.occupe))) break;
  }
  await attendreLibre(p);
  ok('réponse : impulsions de parole (une par mot)', (await p.evaluate(() => window.__imp)) > 8, await p.evaluate(() => window.__imp));
  ok('réponse : impulsions visibles sur la sphère', (await p.evaluate(() => window.__vuesImp)) > 2);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(2500);
  ok('réponse finie : intensité revenue à zéro', (await p.evaluate(() => window.__JARVIS.parole.valeur)) === 0);
  const i0 = await p.evaluate(() => window.__JARVIS.sphere.S.images);
  await p.waitForTimeout(3000);
  const i1 = await p.evaluate(() => window.__JARVIS.sphere.S.images);
  ok('repos : aucune image redessinée en 3 s', i1 === i0, i1 - i0);
  await p.mouse.move(700, 300); await p.mouse.move(720, 320);
  await p.waitForTimeout(300);
  ok('survol : la sphère redessine à la demande', (await p.evaluate(() => window.__JARVIS.sphere.S.images)) > i1);

  // ---------- planification : créer, modifier (glisser), terminer, supprimer ----------
  ok('carte Planification : 3 prochaines tâches', (await p.locator('#planif-liste li button').count()) === 3);
  await p.click('#planif-ouvrir');
  await p.waitForTimeout(1500);
  ok('planification ouverte (semaine)', (await scene(p)) === 'planification');
  await capture(p, 'cockpit-1440x880-planification');
  await p.click('.holo button[data-local="ajouter"]');
  await p.fill('#tache-titre', 'Tâche de test');
  await p.fill('#tache-date', await p.evaluate(() => window.__JARVIS.holo.courant.donnees.aujourd_hui));
  await p.fill('#tache-heure', '15:00');
  await p.selectOption('#tache-priorite', 'haute');
  await p.click('#tache-enregistrer');
  await p.waitForTimeout(1200);
  const trouve = () => p.evaluate(() => window.__JARVIS.holo.courant.donnees.taches.find((t) => t.titre === 'Tâche de test') || null);
  ok('tâche créée (enregistrée directement)', !!(await trouve()));
  const zt = () => p.locator('.holo .zone[aria-label^="Tâche : Tâche de test"]');
  const bb = await zt().boundingBox();
  await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2); await p.mouse.down();
  await p.mouse.move(bb.x + bb.width / 2 + 80, bb.y + bb.height / 2, { steps: 8 }); await p.mouse.up();
  await p.waitForTimeout(1200);
  ok('tâche déplacée à la souris', ((await trouve()) || {}).heure > '15:00', ((await trouve()) || {}).heure);
  await zt().click(); await p.waitForTimeout(300);
  await p.fill('#tache-titre', 'Tâche de test modifiée');
  await p.click('#tache-enregistrer'); await p.waitForTimeout(1200);
  const zm = () => p.locator('.holo .zone[aria-label^="Tâche : Tâche de test modifiée"]');
  ok('tâche modifiée', (await zm().count()) === 1);
  await zm().click(); await p.waitForTimeout(300);
  await p.click('#tache-fait'); await p.waitForTimeout(1200);
  ok('tâche terminée (fait)', (await p.evaluate(() => (window.__JARVIS.holo.courant.donnees.taches.find((t) => t.titre === 'Tâche de test modifiée') || {}).statut)) === 'fait');
  await zm().click(); await p.waitForTimeout(300);
  await p.click('#tache-supprimer'); await p.click('#tache-supprimer'); await p.waitForTimeout(1200);
  ok('tâche supprimée', (await zm().count()) === 0);
  const jr = (await p.textContent('#messages')) || '';
  ok('chaque changement journalisé', ['tâche créée', 'déplacée', 'tâche modifiée', 'tâche fait', 'tâche supprimée'].every((m) => jr.includes(m)));
  await p.selectOption('.holo .controles select', 'tous').catch(async () => p.click('.holo .controles button:has-text("tous")'));
  await p.waitForTimeout(1200);
  ok('vue « tous les projets » en lecture seule', (await p.evaluate(() => window.__JARVIS.holo.courant.donnees.lecture_seule)) && (await p.locator('.holo button[data-local="ajouter"]').count()) === 0);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(600);
  await demander(p, 'Mes tâches de demain');
  ok('JARVIS ouvre la planification (demain, vue jour)', (await p.evaluate(() => window.__JARVIS.holo.courant && window.__JARVIS.holo.courant.donnees.vue)) === 'jour');
  await p.context().close();

  // ---------- iPhone ----------
  const m = await page(nav, { largeur: 390, hauteur: 844 });
  await demander(m, 'Que sais-tu des clients ?');
  ok('iPhone : hologramme fixe', await m.evaluate(() => document.querySelector('.holo').classList.contains('fixe')));
  const larg = await m.evaluate(() => document.documentElement.scrollWidth);
  ok('iPhone : pas de défilement horizontal', larg <= 390, larg);
  await capture(m, 'sphere-390x844-notes-retenues');
  await m.keyboard.press('Escape');
  await m.waitForTimeout(500);
  await m.click('#planif-ouvrir');
  await m.waitForTimeout(1500);
  ok('iPhone : planification', (await scene(m)) === 'planification');
  await capture(m, 'cockpit-390x844-planification');
  await m.context().close();

  // ---------- catalogue (mode démo : 220 neurones) ----------
  const c = await page(nav, { chemin: '/sphere/catalogue.html' });
  ok('catalogue en mode démo', await c.evaluate(() => window.__JARVIS.mode === 'demo'));
  ok('démo : rien à valider au démarrage', (await c.textContent('#nb-a-valider')).trim() === '0');
  ok('démo : 220 neurones', (await c.textContent('#compteur')).startsWith('220 neurones'));
  const attendu = { 'Notes retenues': 'notes_retenues', 'Tous les projets': 'notes_retenues', Planification: 'planification', 'Graphique 3D': 'graphique',
    Machine: 'machine', Météo: 'meteo', 'Résumé de la nuit': 'resume_nuit', 'Note sensible refusée': 'note_privee',
    'Scène inconnue': 'carte_projets' };
  for (const [bouton, sc] of Object.entries(attendu)) {
    await c.click(`#catalogue-liste button:has-text("${bouton}")`);
    await c.waitForTimeout(300);
    await attendreLibre(c);
    await c.waitForTimeout(500);
    ok(`catalogue : ${bouton}`, (await scene(c)) === sc, await scene(c));
    if (sc === 'meteo') await capture(c, 'catalogue-1440x880-meteo');
    if (sc === 'graphique') await capture(c, 'catalogue-1440x880-graphique');
  }
  await c.click('#catalogue-liste button:has-text("Événement invalide")');
  ok('catalogue : événement invalide refusé', (await c.textContent('#catalogue-sortie')).startsWith('Refusé'));
  const nuit = new Set();
  await c.click('#catalogue-liste button:has-text("Nuit simulée")');
  for (let i = 0; i < 60; i++) {
    const t = (await c.textContent('#phase')) || '';
    const mm = /NUIT · (\d)/.exec(t);
    if (mm) nuit.add(mm[1]);
    await c.waitForTimeout(250);
    if (!(await c.evaluate(() => window.__JARVIS.occupe))) break;
  }
  await attendreLibre(c);
  ok('nuit : 4 phases vues', ['1', '2', '3', '4'].every((x) => nuit.has(x)), [...nuit].join(','));
  ok('nuit : propositions jaunes « À valider »', Number(await c.textContent('#nb-a-valider')) === 3);
  ok('nuit : anneaux jaunes sur la sphère', await c.evaluate(() => window.__JARVIS.sphere.S.alertes.length === 3));
  await capture(c, 'catalogue-1440x880-apres-la-nuit');
  await c.context().close();

  // ---------- mouvement réduit ----------
  const rm = await page(nav, { options: { reducedMotion: 'reduce' } });
  ok('mouvement réduit : pas de déformation par la voix', await rm.evaluate(() => window.__JARVIS.sphere.S.U.uDeform.value === 0));
  await rm.context().close();
} catch (e) {
  bilan.erreurs.push('exception : ' + e.message);
} finally {
  await nav.close();
}

// ---------- sans WebGL : message clair et liste des notes ----------
const sansGL = await playwright.chromium.launch({ args: ['--disable-webgl', '--disable-3d-apis'] });
try {
  const ctx = await sansGL.newContext({ viewport: { width: 1440, height: 880 } });
  const p = await ctx.newPage();
  await p.goto(`${base}/?jeton=${jeton}`);
  await p.waitForFunction(() => window.__JARVIS && window.__JARVIS.pret, null, { timeout: 45000 });
  ok('sans WebGL : message et liste des notes', await p.isVisible('#sansgl') && (await p.locator('#sansgl li').count()) > 5);
} catch (e) {
  bilan.erreurs.push('sans WebGL : ' + e.message);
} finally {
  await sansGL.close();
}
console.log(JSON.stringify(bilan));
