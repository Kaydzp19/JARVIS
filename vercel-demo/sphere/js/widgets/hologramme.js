// Moteur des hologrammes (affichés à la demande, un seul à la fois).
//
// JARVIS écrit un événement d'affichage (scène + données) ; l'interface construit le widget :
// - un panneau 3D (texture canvas 2D sur un plan) : coins lumineux, grille, lignes de balayage,
//   léger décalage chromatique, apparition par une ligne qui balaie (« line-reveal scan ») ;
// - un objet 3D en fil de fer qui tourne (Kayd peut le tourner et le zoomer) ;
// - un calque de vrais boutons par-dessus (accessibles au clavier et au toucher) :
//   déplacer, redimensionner, épingler, fermer, période, onglets, filtres, tri, actions,
//   zones survolables (barres, points, lignes) et notes cliquables.
// Fermeture : après un délai (mis en pause pendant l'interaction), ×, ou Échap.
// Une action qui écrit, supprime, publie ou paie n'est jamais exécutée ici : elle part
// au serveur qui en fait une proposition « à valider ».

import * as THREE from 'three';
import { el, memoire, mouvementReduit } from '../outils.js';
import { construireHeros, liberer } from './heros.js';
import { creerRegistre, dureeAffichage } from './registre.js';
import { sceneDe } from './scenes/index.js';

const WV = 'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
const WF = `uniform sampler2D uTex;uniform float uProg;uniform float uTime;uniform float uRows;varying vec2 vUv;
void main(){float e=1.0-vUv.y;float front=uProg*1.25-0.12;float m=1.0-smoothstep(front-0.05,front,e);
float line=exp(-pow((e-front)*55.0,2.0))*(1.0-smoothstep(0.92,1.0,uProg));
float sh=0.0015*(1.0-uProg);vec4 t=texture2D(uTex,vUv);float r=texture2D(uTex,vUv+vec2(sh+0.0012,0.0)).r;float b=texture2D(uTex,vUv-vec2(sh+0.0012,0.0)).b;
float sl=0.94+0.06*sin(vUv.y*uRows+uTime*2.0);float fl=0.95+0.05*sin(uTime*37.0)*step(0.9,fract(sin(floor(uTime*7.0))*43758.5));
vec3 col=vec3(r,t.g,b)*sl*fl;float a=t.a*m*(uProg>0.001?1.0:0.0);
col+=vec3(0.35,0.8,1.0)*line;a=max(a,line*0.85*step(0.001,uProg));gl_FragColor=vec4(col,min(1.0,a)*min(1.0,uProg*6.0));}`;
const EPINGLE = '<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 1h6l-1 5 3 3H3l3-3z M8 9v6" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>';
const LIBELLES_TRI = { rang: 'rang', score: 'score', titre: 'titre', cpu: 'processeur', ram: 'mémoire', nom: 'nom' };

export function creerHologrammes({ sphere, centre, surAction, surNote, surOuvrirNote, annoncer, vivant }) {
  const S = sphere.S, reduit = mouvementReduit();
  const registre = creerRegistre();
  const groupe = new THREE.Group();
  groupe.visible = false;
  S.scene.add(groupe);
  const contenu = new THREE.Group();          // unités = pixels du widget
  groupe.add(contenu);
  const toile = document.createElement('canvas'), ctx = toile.getContext('2d');
  let tex = new THREE.CanvasTexture(toile);
  const mat = new THREE.ShaderMaterial({ uniforms: { uTex: { value: tex }, uProg: { value: 0 }, uTime: S.U.uTime, uRows: { value: 300 } },
    vertexShader: WV, fragmentShader: WF, transparent: true, depthWrite: false });
  const plan = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
  contenu.add(plan);

  // ---- calque DOM ----
  const calque = el('div', 'holo');
  calque.hidden = true; calque.tabIndex = -1; calque.setAttribute('role', 'region');
  const poignee = el('div', 'poignee'); poignee.tabIndex = 0;
  const herosEl = el('div', 'heros'); herosEl.tabIndex = 0; herosEl.hidden = true;
  herosEl.setAttribute('role', 'img');
  herosEl.setAttribute('aria-label', 'Objet 3D : glisser ou flèches pour le tourner, molette ou + et - pour zoomer');
  const zonesEl = el('div'), controles = el('div', 'controles'), redim = el('div', 'redim'), info = el('div', 'info');
  info.hidden = true;
  const outils = el('div', 'outils');
  const bEpingle = el('button'); bEpingle.type = 'button'; bEpingle.innerHTML = EPINGLE;
  bEpingle.setAttribute('aria-pressed', 'false'); bEpingle.setAttribute('aria-label', 'Épingler (l’hologramme ne se ferme plus tout seul)');
  const bFermer = el('button', '', '×'); bFermer.type = 'button'; bFermer.setAttribute('aria-label', 'Fermer l’hologramme (Échap)');
  outils.append(bEpingle, bFermer);
  calque.append(poignee, zonesEl, herosEl, controles, outils, redim, info);
  centre.appendChild(calque);

  const o = { ev: null, scene: null, ui: {}, prog: 0, cible: 0, boite: null, Wd: 0, Hd: 0, heros: null, herosCle: '',
    zonesCle: '', zones: [], ttl: 0, epingle: false, survol: false, focus: false, glisse: false, visible: false,
    precedent: null, polices: false, redessin: 0, infoFixe: null, herosRect: null };
  const fixe = () => S.W < 560 || (window.matchMedia && window.matchMedia('(max-width: 900px)').matches);

  Promise.race([
    Promise.all([document.fonts ? document.fonts.load('700 20px Rajdhani') : 0, document.fonts ? document.fonts.load('400 12px "JetBrains Mono"') : 0]).catch(() => {}),
    new Promise((r) => setTimeout(r, 1800)),
  ]).then(() => { o.polices = true; if (o.ev) dessiner(); });

  // ---- position et taille ----
  function boiteParDefaut(disp) {
    const W = S.W, H = S.H, port = H > W * 1.05;
    const rc = disp === 'pleine' ? { x0: -0.92, x1: 0.92, y0: -0.80, y1: port ? 0.34 : 0.26 } : { x0: -0.9, x1: 0.9, y0: -0.80, y1: port ? -0.36 : -0.32 };
    let w = (rc.x1 - rc.x0) / 2 * W;
    const h = (rc.y1 - rc.y0) / 2 * H, ratio = disp === 'pleine' ? 1.75 : 4.4;
    if (w / h > ratio) w = h * ratio;
    const px = ((rc.x0 + rc.x1) / 4 + 0.5) * W, py = (-(rc.y0 + rc.y1) / 4 + 0.5) * H;
    return { x: px - w / 2, y: py - h / 2, w, h: Math.max(disp === 'pleine' ? 220 : 130, h) };
  }
  function borner(b) {
    const w = Math.max(260, Math.min(S.W, b.w)), h = Math.max(130, Math.min(S.H, b.h));
    return { w, h, x: Math.max(0, Math.min(S.W - w, b.x)), y: Math.max(0, Math.min(S.H - h, b.y)) };
  }
  const disposition = () => (typeof o.scene.disposition === 'function' ? o.scene.disposition(o.ev) : o.scene.disposition);
  const cleMemoire = () => 'jarvis.holo.' + disposition();
  function boiteInitiale() {
    if (!fixe()) {
      const m = memoire.lire(cleMemoire());
      if (m && m.fw > 0 && m.fh > 0) return borner({ x: m.fx * S.W, y: m.fy * S.H, w: m.fw * S.W, h: m.fh * S.H });
    }
    return borner(boiteParDefaut(disposition()));
  }
  function memoriser() {
    if (fixe()) return;
    const b = o.boite;
    memoire.ecrire(cleMemoire(), { fx: b.x / S.W, fy: b.y / S.H, fw: b.w / S.W, fh: b.h / S.H });
  }
  function placer() {
    const b = o.boite, pr = sphere.pointEcran(b.x + b.w / 2, b.y + b.h / 2, 1.0);
    const f = (b.w / S.W * 2 * pr.hw) / Math.max(1, o.Wd || b.w);
    groupe.position.set(pr.x, pr.y, 1.0);
    contenu.scale.set(f, f, f);
    plan.scale.set(o.Wd || b.w, o.Hd || b.h, 1);
    Object.assign(calque.style, { left: b.x + 'px', top: b.y + 'px', width: b.w + 'px', height: b.h + 'px' });
    calque.classList.toggle('fixe', fixe());
  }

  // ---- dessin ----
  function dessiner() {
    if (!o.ev || !o.polices) return;
    const W = Math.round(o.boite.w), H = Math.round(o.boite.h), ts = Math.min(2.5, (window.devicePixelRatio || 1) * 1.25);
    if (toile.width !== Math.round(W * ts) || toile.height !== Math.round(H * ts)) {
      toile.width = Math.round(W * ts); toile.height = Math.round(H * ts);
      tex.dispose(); tex = new THREE.CanvasTexture(toile); mat.uniforms.uTex.value = tex;
    }
    tex.minFilter = THREE.LinearFilter; tex.generateMipmaps = false;
    ctx.setTransform(ts, 0, 0, ts, 0, 0);
    o.Wd = W; o.Hd = H;
    let res;
    try { res = o.scene.dessiner(ctx, W, H, o.ev, o.ui) || {}; } catch (e) {
      res = sceneDe('?').dessiner(ctx, W, H, o.ev, o.ui) || {};           // jamais d'erreur à l'écran
    }
    tex.needsUpdate = true;
    mat.uniforms.uRows.value = H * 0.9;
    const h = res.heros;
    const cle = h ? JSON.stringify(h) + W + 'x' + H : '';
    if (cle !== o.herosCle) {
      if (o.heros) { contenu.remove(o.heros); liberer(o.heros); o.heros = null; }
      o.herosCle = cle;
      if (h) {
        o.heros = construireHeros(h, 1, W, H, () => (vivant && vivant() ? vivant().cpu : 30));
        if (o.heros) { o.heros.position.z = 18; contenu.add(o.heros); }
      }
      o.herosRect = h ? { x: h.x, y: h.y, w: h.w, h: h.h } : null;
      herosEl.hidden = !o.herosRect;
      if (o.herosRect) Object.assign(herosEl.style, { left: h.x + 'px', top: h.y + 'px', width: h.w + 'px', height: h.h + 'px' });
    }
    majZones(res.zones || []);
    placer();
  }

  function majZones(zones) {
    o.zones = zones;
    const cle = JSON.stringify(zones.map((z) => [z.id, Math.round(z.x), Math.round(z.y), Math.round(z.w), Math.round(z.h)]));
    if (cle === o.zonesCle) {
      Array.from(zonesEl.children).forEach((b, i) => {
        b.setAttribute('aria-label', zones[i].label);
        if (zones[i].type === 'note') b.setAttribute('aria-pressed', o.ui.selection === zones[i].id ? 'true' : 'false');
      });
      return;
    }
    o.zonesCle = cle;
    zonesEl.textContent = '';
    zones.forEach((z, i) => {
      const b = el('button', 'zone');
      b.type = 'button';
      Object.assign(b.style, { left: z.x + 'px', top: z.y + 'px', width: z.w + 'px', height: z.h + 'px' });
      b.setAttribute('aria-label', z.label);
      if (z.type === 'note') b.setAttribute('aria-pressed', o.ui.selection === z.id ? 'true' : 'false');
      const montrer = () => montrerInfo(o.zones[i]);
      b.addEventListener('pointerenter', montrer);
      b.addEventListener('focus', montrer);
      b.addEventListener('pointerleave', () => { if (o.infoFixe !== z.id) cacherInfo(); });
      b.addEventListener('blur', () => { if (o.infoFixe !== z.id) cacherInfo(); });
      b.addEventListener('click', () => cliquerZone(o.zones[i]));
      zonesEl.appendChild(b);
    });
  }
  function montrerInfo(z) {
    if (!z) return;
    info.textContent = '';
    info.appendChild(document.createTextNode(z.info ? z.info[0] : z.label));
    if (z.info && z.info[1]) info.appendChild(el('small', '', z.info[1]));
    info.style.left = Math.max(60, Math.min(o.boite.w - 60, z.x + z.w / 2)) + 'px';
    info.style.top = Math.max(30, z.y) + 'px';
    info.hidden = false;
  }
  function cacherInfo() { info.hidden = true; }
  function cliquerZone(z) {
    if (z.type === 'note') {
      o.ui.selection = o.ui.selection === z.id ? null : z.id;
      if (o.ui.selection && surNote) surNote(z.note);
      dessiner(); majActions();
      return;
    }
    o.infoFixe = o.infoFixe === z.id ? null : z.id;
    if (o.infoFixe) montrerInfo(z); else cacherInfo();
  }

  // ---- contrôles et actions ----
  function noteChoisie() {
    const z = o.zones.find((x) => x.id === o.ui.selection);
    return z && z.note;
  }
  function majActions() {
    controles.querySelectorAll('button[data-action="ouvrir_note"]').forEach((b) => {
      const n = noteChoisie();
      b.disabled = !n;
      b.title = n ? '' : 'Choisis d’abord une note dans la liste';
    });
  }
  function construireControles() {
    controles.textContent = '';
    const c = o.ev.controles || {};
    const groupeBoutons = (valeurs, cle, surChoix, etiquette) => {
      const g = el('div'); g.setAttribute('role', 'group'); g.setAttribute('aria-label', etiquette);
      g.style.display = 'flex'; g.style.gap = '4px';
      valeurs.forEach((v) => {
        const b = el('button', '', v); b.type = 'button';
        b.setAttribute('aria-pressed', o.ui[cle] === v ? 'true' : 'false');
        b.addEventListener('click', () => {
          o.ui[cle] = o.ui[cle] === v && cle === 'filtreChoix' ? null : v;
          g.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', x.textContent === o.ui[cle] ? 'true' : 'false'));
          surChoix(v);
        });
        g.appendChild(b);
      });
      controles.appendChild(g);
    };
    if (c.onglets) groupeBoutons(c.onglets, 'onglet', () => dessiner(), 'Onglets');
    if (c.filtres) groupeBoutons(c.filtres, 'filtreChoix', () => dessiner(), 'Filtres');
    if (c.periode) groupeBoutons(c.periode, 'periode', (p) => surAction(o.ev, 'periode', { periode: p }), 'Période');
    if (o.scene.filtreTexte) {
      const i = el('input'); i.type = 'search'; i.placeholder = 'filtrer'; i.setAttribute('aria-label', 'Filtrer la liste');
      i.value = o.ui.filtre || '';
      i.addEventListener('input', () => { o.ui.filtre = i.value; dessiner(); });
      controles.appendChild(i);
    }
    if (c.tri) {
      const s = el('select'); s.setAttribute('aria-label', 'Trier');
      c.tri.forEach((v) => { const op = el('option', '', 'tri : ' + (LIBELLES_TRI[v] || v)); op.value = v; s.appendChild(op); });
      s.value = o.ui.tri || c.tri[0];
      s.addEventListener('change', () => { o.ui.tri = s.value; dessiner(); });
      controles.appendChild(s);
    }
    (o.ev.actions || []).forEach((a) => {
      const ecrit = a.type === 'ecriture';
      const b = el('button', ecrit ? 'ecrire' : '', ecrit ? `${a.libelle} · à valider` : a.libelle);
      b.type = 'button'; b.dataset.action = a.id;
      if (ecrit) b.setAttribute('aria-label', `${a.libelle} : crée une proposition à valider, rien n’est exécuté ici`);
      b.addEventListener('click', () => {
        if (a.id === 'ouvrir_note') { const n = noteChoisie(); if (n) surOuvrirNote(n); return; }
        if (a.id === 'ouvrir_note_locale') {          // geste de Kayd, sur sa machine (jamais JARVIS)
          surOuvrirNote({ projet: o.ev.projet, id: o.ev.donnees.id, sensible: true, parKayd: true });
          return;
        }
        const n = noteChoisie();
        surAction(o.ev, a.id, n ? { note: n.id } : {});
      });
      controles.appendChild(b);
    });
    majActions();
  }

  // ---- ouvrir, mettre à jour, fermer ----
  function appliquer(brut) {
    const r = registre.appliquer(brut);
    if (r.geste === 'refuser' || r.geste === 'ignorer') return r;
    if (r.geste === 'mettre_a_jour' && o.visible && o.ev && o.ev.id === r.ev.id) {
      o.ev = r.ev;
      if (r.ev.donnees.periode) o.ui.periode = r.ev.donnees.periode;
      dessiner();
      if (annoncer) annoncer(`Hologramme mis à jour : ${r.ev.titre}.`);
      return r;
    }
    ouvrir(r.ev);
    return r;
  }
  function ouvrir(ev) {
    if (!o.visible) o.precedent = document.activeElement;
    nettoyer();
    o.ev = ev; o.scene = sceneDe(ev.scene);
    const c = ev.controles || {};
    o.ui = { tri: c.tri ? c.tri[0] : null, periode: ev.donnees.periode || null, onglet: c.onglets ? c.onglets[0] : null,
      filtre: '', filtreChoix: null, selection: null };
    o.ttl = dureeAffichage(ev); o.epingle = false; o.infoFixe = null;
    bEpingle.setAttribute('aria-pressed', 'false');
    o.boite = boiteInitiale();
    o.visible = true; groupe.visible = true; o.prog = reduit ? 0.98 : 0; o.cible = 1;
    calque.hidden = false;
    calque.setAttribute('aria-label', `Hologramme : ${ev.titre}`);
    poignee.setAttribute('aria-label', `${ev.titre} : déplacer avec les flèches, Maj + flèches pour redimensionner`);
    const port = S.H > S.W * 1.05;
    sphere.compacter(true, disposition() === 'pleine' ? 1 : (port ? 0.33 : 0.36));
    construireControles();
    dessiner();
    // Le focus reste dans la conversation ; l'hologramme est annoncé et joignable avec Tab.
    if (annoncer) annoncer(`Hologramme affiché : ${ev.titre}. Échap pour fermer.`);
  }
  function nettoyer() {
    if (o.heros) { contenu.remove(o.heros); liberer(o.heros); o.heros = null; }
    o.herosCle = ''; o.zonesCle = ''; zonesEl.textContent = ''; cacherInfo();
  }
  function fermer() {
    if (!o.visible || o.cible === 0) return;
    o.cible = 0;
    const avaitFocus = calque.contains(document.activeElement);
    calque.hidden = true;
    sphere.compacter(false);
    registre.fermer();
    if (avaitFocus && o.precedent && o.precedent.focus && document.contains(o.precedent)) o.precedent.focus({ preventScroll: true });
    if (annoncer) annoncer('Hologramme fermé.');
  }

  // ---- interactions : survol, focus, glisser, redimensionner, objet 3D ----
  calque.addEventListener('pointerenter', () => { o.survol = true; });
  calque.addEventListener('pointerleave', () => { o.survol = false; });
  calque.addEventListener('focusin', () => { o.focus = true; });
  calque.addEventListener('focusout', (e) => { if (!calque.contains(e.relatedTarget)) o.focus = false; });
  bFermer.addEventListener('click', fermer);
  bEpingle.addEventListener('click', () => {
    o.epingle = !o.epingle;
    bEpingle.setAttribute('aria-pressed', o.epingle ? 'true' : 'false');
    if (annoncer) annoncer(o.epingle ? 'Hologramme épinglé.' : 'Hologramme désépinglé.');
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || !o.visible || o.cible === 0) return;
    const dlg = document.getElementById('editeur');
    if (dlg && dlg.open) return;
    fermer();
  });
  function glisser(element, surMouvement) {
    element.addEventListener('pointerdown', (e) => {
      if (fixe() && element !== herosEl) return;
      e.preventDefault();
      element.setPointerCapture(e.pointerId);
      o.glisse = true;
      let x = e.clientX, y = e.clientY;
      const bouger = (m) => { surMouvement(m.clientX - x, m.clientY - y); x = m.clientX; y = m.clientY; };
      const finir = () => {
        o.glisse = false;
        element.removeEventListener('pointermove', bouger);
        element.removeEventListener('pointerup', finir);
        element.removeEventListener('pointercancel', finir);
        if (element !== herosEl) memoriser();
      };
      element.addEventListener('pointermove', bouger);
      element.addEventListener('pointerup', finir);
      element.addEventListener('pointercancel', finir);
    });
  }
  let redessinPrevu = false;
  const redessinerBientot = () => {
    if (redessinPrevu) return;
    redessinPrevu = true;
    requestAnimationFrame(() => { redessinPrevu = false; dessiner(); });
  };
  glisser(poignee, (dx, dy) => { o.boite = borner({ ...o.boite, x: o.boite.x + dx, y: o.boite.y + dy }); placer(); });
  glisser(redim, (dx, dy) => { o.boite = borner({ ...o.boite, w: o.boite.w + dx, h: o.boite.h + dy }); placer(); redessinerBientot(); });
  poignee.addEventListener('keydown', (e) => {
    const d = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] }[e.key];
    if (!d || fixe()) return;
    e.preventDefault();
    o.boite = borner(e.shiftKey ? { ...o.boite, w: o.boite.w + d[0], h: o.boite.h + d[1] } : { ...o.boite, x: o.boite.x + d[0], y: o.boite.y + d[1] });
    if (e.shiftKey) dessiner(); else placer();
    memoriser();
  });
  const tournerHeros = (dx, dy) => { if (o.heros) { const r = o.heros.userData.rotation; r.y += dx * 0.012; r.x = Math.max(-1.2, Math.min(1.2, r.x + dy * 0.012)); } };
  const zoomerHeros = (k) => { if (o.heros) o.heros.userData.zoom = Math.max(0.6, Math.min(1.8, o.heros.userData.zoom * k)); };
  glisser(herosEl, tournerHeros);
  herosEl.addEventListener('wheel', (e) => { e.preventDefault(); zoomerHeros(Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  herosEl.addEventListener('keydown', (e) => {
    const d = { ArrowLeft: [-15, 0], ArrowRight: [15, 0], ArrowUp: [0, -15], ArrowDown: [0, 15] }[e.key];
    if (d) { e.preventDefault(); tournerHeros(d[0], d[1]); } else if (e.key === '+' || e.key === '=') zoomerHeros(1.12);
    else if (e.key === '-') zoomerHeros(1 / 1.12);
  });
  S.auRedimensionnement.push(() => { if (o.visible && o.ev && o.cible > 0) { o.boite = boiteInitiale(); dessiner(); } });
  const pp = { x: 0, y: 0 };
  centre.addEventListener('pointermove', (e) => {
    const r = centre.getBoundingClientRect();
    pp.x = ((e.clientX - r.left) / r.width - 0.5) * 2; pp.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
  });

  // ---- animation (appelée à chaque image par la sphère) ----
  S.etapes.push((dt, maintenant) => {
    if (!o.visible) return;
    const vitesse = reduit ? 8 : (o.cible > o.prog ? 1.5 : 2.2);
    o.prog += Math.max(-1, Math.min(1, o.cible - o.prog)) * Math.min(1, vitesse * dt * 2.2);
    const enPause = o.epingle || o.survol || o.focus || o.glisse;
    if (o.cible > 0 && dureeAffichage(o.ev) > 0 && !enPause) { o.ttl -= dt; if (o.ttl <= 0) fermer(); }
    if (o.cible === 0 && o.prog < 0.01) {
      o.prog = 0; groupe.visible = false; o.visible = false; nettoyer(); o.ev = null;
      return;
    }
    mat.uniforms.uProg.value = Math.min(1, o.prog);
    const t = maintenant / 1000;
    placer();
    groupe.rotation.y = reduit ? 0 : Math.sin(t * 0.5) * 0.04 + pp.x * 0.05;
    groupe.rotation.x = reduit ? 0 : -0.02 + pp.y * 0.03;
    if (o.heros) {
      const u = o.heros.userData, obj = u.objet, ud = obj.userData;
      if (ud.tick && !reduit) ud.tick(t, o.prog); else if (ud.tick) ud.tick(0, 1);
      obj.rotation.y += u.rotation.y; obj.rotation.x += u.rotation.x;
      obj.scale.setScalar(u.base * u.zoom);
      const op = Math.min(1, o.prog * 1.2);
      (ud.mats || []).forEach((m) => { m.opacity = ud.remplir && m.type === 'MeshBasicMaterial' ? op * 0.2 : op * 0.9; });
      (ud.extra || []).forEach((m) => { m.opacity = op * 0.9; });
    }
    if (o.scene && o.scene.vivant && vivant) {
      o.redessin += dt;
      if (o.redessin > 1) { o.redessin = 0; const v = vivant(); if (v) { o.ui.vivant = v; dessiner(); } }
    }
  });

  return {
    appliquer, fermer,
    get courant() { return o.visible && o.cible > 0 ? o.ev : null; },
    get visible() { return o.visible && o.cible > 0; },
    get ui() { return o.ui; },
    get heros() { return o.heros ? { ...o.heros.userData.rotation, zoom: o.heros.userData.zoom } : null; },
  };
}
