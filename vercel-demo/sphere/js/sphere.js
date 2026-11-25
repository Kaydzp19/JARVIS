// La sphère : un neurone par note, une synapse par lien pondéré, une région par projet.
// Un seul objet THREE.Points (shaders maison, mélange additif) : neurones, poussière de
// surface et de volume, et synapses en POINTILLÉS IMMOBILES le long de courbes de Bézier
// (densité et intensité selon le poids). Aucune forme de cerveau.
//
// Rendu À LA DEMANDE : au repos la sphère est une image fixe, rien n'est recalculé ni
// redessiné. On ne dessine que pendant une interaction (glisser, zoom, survol), une
// animation (vague de recherche, réponse de JARVIS, nuit) ou un hologramme ouvert.
// Pas de rotation automatique.
//
// Quand JARVIS répond, chaque impulsion de parole part de la zone du projet concerné et
// traverse la sphère (neurones plus gros et plus lumineux, synapses éclairées, léger
// gonflement), en bleu vif. L'orange reste réservé à la recherche de notes.
//
// L'interface LIT les données ; la sphère n'en modifie aucune.

import * as THREE from 'three';
import { el, mouvementReduit, rng } from './outils.js';
import { installerVague } from './vague.js';
import { installerNuit } from './nuit.js';

const V3 = THREE.Vector3;
const MAXP = 24000;
const TH = Math.tan(20 * Math.PI / 180);

const VERT = `attribute vec3 aP0;attribute vec3 aP1;attribute vec3 aP2;attribute vec4 aA;attribute vec4 aB;attribute vec2 aC;
uniform float uK;uniform float uCam;uniform float uDeform;uniform float uListen;uniform float uVif;
uniform float uGlobal;uniform float uScl;uniform vec3 uWD;uniform float uWR;uniform float uWAmp;uniform float uDim;uniform float uPous;
uniform vec4 uPI[4];uniform float uPF[4];
varying vec3 vC;varying float vA;varying float vW;
void main(){float kind=aC.x;vec3 p=aP0;float t=0.0;
if(kind>1.5&&kind<2.5){t=aA.x;p=mix(mix(aP0,aP1,t),mix(aP1,aP2,t),t);}
vec3 dir=normalize(p+vec3(0.0001));
float pul=0.0;
for(int i=0;i<4;i++){if(uPI[i].w>=0.0){float ang=acos(clamp(dot(dir,uPI[i].xyz),-1.0,1.0));
float d=ang-uPI[i].w*2.8;float onde=uDeform>0.5?exp(-d*d*7.0):1.0;pul+=uPF[i]*onde*exp(-uPI[i].w*1.6);}}
pul=min(pul,1.0);
float rad=1.0+uDeform*pul*0.03-uListen*0.035;p*=rad;
vec4 mv=modelViewMatrix*vec4(p,1.0);
float act=kind>1.5?mix(aB.x,aB.y,t):aB.x;
float wa=0.0;if(uWR>-5.0){vec2 q=mv.xy/uScl;float pq=dot(q,vec2(-uWD.y,uWD.x));float dd=dot(q,uWD.xy)+0.3*pq*pq-uWR;
wa=uWAmp*(exp(-dd*dd*15.0)+step(dd,0.0)*0.24*exp(dd*1.3));}
act=max(act,wa*(kind<0.5?0.75:1.0));
float fade=clamp(1.12-(-mv.z-(uCam-1.0))*0.36,0.22,1.2);
float pous=kind<0.5?uPous:1.0;
float neur=abs(kind-1.0)<0.5?1.0:0.0;
float md=step(0.5,aB.w);
float size=aA.z*uScl*(1.0+act*(neur>0.5?3.3:2.0)+md*0.6+uDeform*pul*(neur>0.5?1.6:0.8))*aB.z*pous;
gl_PointSize=aB.z*pous>0.01?max(1.4,size*uK/(-mv.z)):0.0;
vec3 base=mix(vec3(0.22,0.66,1.0),vec3(0.78,0.96,1.0),aA.w*aA.w);
base=mix(base,vec3(0.36,0.84,1.0),uVif*0.55);
base=mix(base,vec3(0.72,0.95,1.0),pul*0.6);
float yel=step(0.5,aB.w)*step(aB.w,1.5);float ora=step(1.5,aB.w)*0.9;
vec3 c=mix(base,vec3(1.0,0.85,0.30),yel);c=mix(c,vec3(1.0,0.54,0.24),max(act,ora));
vC=c;vW=1.0-max(max(yel,ora),act);
float lum=1.0+uVif*0.35+pul*(kind>1.5?2.2:1.4);
vA=fade*aB.z*pous*uGlobal*(0.5+0.5*aA.w)*lum*(1.0+act*1.0+md*0.5)*(1.0-uDim*0.64*(1.0-clamp(act*1.7,0.0,1.0)));
gl_Position=projectionMatrix*mv;}`;
const FRAG = `varying vec3 vC;varying float vA;varying float vW;
void main(){float d=length(gl_PointCoord-vec2(0.5));if(d>0.5)discard;
float g=smoothstep(0.5,0.0,d);g*=g;float core=smoothstep(0.24,0.02,d);
vec3 c=vC*(0.7+core*0.8*vW)+vec3(core*0.14*vW);gl_FragColor=vec4(c,min(1.0,g*0.8+core*0.7)*min(vA,1.3));}`;
const FRING = `varying vec3 vC;varying float vA;varying float vW;
void main(){float d=length(gl_PointCoord-vec2(0.5));float a=smoothstep(0.06,0.0,abs(d-0.37));if(a<0.01)discard;gl_FragColor=vec4(vC,a*min(vA,1.0));}`;

function creerGeometrie(n) {
  const g = new THREE.BufferGeometry();
  const a = { p0: new Float32Array(n * 3), p1: new Float32Array(n * 3), p2: new Float32Array(n * 3),
    a: new Float32Array(n * 4), b: new Float32Array(n * 4), c: new Float32Array(n * 2) };
  const p0 = new THREE.BufferAttribute(a.p0, 3);
  g.setAttribute('position', p0); g.setAttribute('aP0', p0);
  g.setAttribute('aP1', new THREE.BufferAttribute(a.p1, 3));
  g.setAttribute('aP2', new THREE.BufferAttribute(a.p2, 3));
  g.setAttribute('aA', new THREE.BufferAttribute(a.a, 4));
  g.setAttribute('aB', new THREE.BufferAttribute(a.b, 4));
  g.setAttribute('aC', new THREE.BufferAttribute(a.c, 2));
  return { g, a };
}

/** Directions des régions : 3 projets comme la maquette, sinon réparties (spirale de Fibonacci). */
function centresRegions(n) {
  if (n === 3) return [new V3(-0.62, 0.25, 0.74), new V3(0.62, 0.25, 0.74), new V3(0, 0.2, -1)].map((v) => v.normalize());
  if (n === 2) return [new V3(-0.7, 0.2, 0.68), new V3(0.7, 0.2, 0.68)].map((v) => v.normalize());
  const c = [];
  for (let i = 0; i < n; i++) {
    const y = 1 - (i + 0.5) / n * 2, r = Math.sqrt(1 - y * y), t = i * 2.39996;
    c.push(new V3(r * Math.cos(t), y * 0.8, r * Math.sin(t)).normalize());
  }
  return c;
}

/**
 * Crée la sphère dans « conteneur ». Renvoie null si WebGL est absent.
 * options : { auChangement(compteurs), auSurvol(info), annoncer(texte) }
 */
export function creerSphere(conteneur, options = {}) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (e) {
    return null;
  }
  if (!renderer.getContext()) return null;
  const reduit = mouvementReduit();
  let DPR = Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(DPR);
  renderer.setClearColor(0x000000, 0);
  const cv = renderer.domElement;
  cv.tabIndex = 0;
  cv.setAttribute('role', 'img');
  cv.setAttribute('aria-label', 'Sphère de neurones et de synapses : la mémoire de JARVIS, une région par projet. '
    + 'Une vague orange la parcourt quand il cherche. Glisser ou flèches : tourner ; molette, pincement, + et - : zoomer ; '
    + 'Entrée : choisir le neurone le plus proche du centre.');
  const anneau = conteneur.querySelector('#anneau'), bulle = conteneur.querySelector('#bulle');
  const etiquettes = conteneur.querySelector('#etiquettes');
  conteneur.insertBefore(cv, anneau);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 60);
  const U = { uTime: { value: 0 }, uK: { value: 600 }, uCam: { value: 4 }, uDeform: { value: reduit ? 0 : 1 },
    uListen: { value: 0 }, uVif: { value: 0 }, uGlobal: { value: 1 }, uScl: { value: 1 },
    uWD: { value: new V3(1, 0, 0) }, uWR: { value: -9 }, uWAmp: { value: 0 }, uDim: { value: 0 }, uPous: { value: 1 },
    uPI: { value: [0, 1, 2, 3].map(() => new THREE.Vector4(0, 0, 1, -1)) }, uPF: { value: [0, 0, 0, 0] } };
  const materiau = (frag, u) => new THREE.ShaderMaterial({ uniforms: u || U, vertexShader: VERT, fragmentShader: frag,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const matPoints = materiau(FRAG);
  const matAnneaux = materiau(FRING, { ...U, uWR: { value: -9 }, uDim: { value: 0 } });
  const sph = new THREE.Group();
  scene.add(sph);

  // Contexte partagé avec la vague, la nuit et les hologrammes.
  const S = {
    THREE, U, sph, scene, camera, renderer, cv, TH, reduit, etiquettes,
    noeuds: [], aretes: [], N: 0, parProjet: [], projets: [], index: new Map(),
    act: new Float32Array(0), eact: new Float32Array(0), useE: false, focus: -1, focDim: 0.4,
    selection: -1, survol: -1, alertes: [], arch: 0, actSale: false,
    ecoute: 0, ecouteCible: 0, mode: 0, modeT: 0, compactActif: false, vif: 0, impulsions: [],
    W: 800, H: 600, D: 4, zoom: 1, asp: 1, glisse: false, ecran: [],
    etapes: [], besoins: [], auRedimensionnement: [], vague: null, nuitS: null, parole: null,
  };

  // ------------------------------------------------------------------
  // Construction à partir des données (titres, identifiants, poids)
  // ------------------------------------------------------------------
  let pts = null, anneaux = null;

  function vider() {
    [pts, anneaux].forEach((o) => { if (o) { sph.remove(o); o.geometry.dispose(); } });
    pts = anneaux = null;
  }

  function charger(donnees) {
    vider();
    const projets = donnees.projets || [];
    const rnd = rng(23);
    const CEN = centresRegions(Math.max(1, projets.length));
    const region = (d) => {
      let b = -1, v1 = -9, v2 = -9;
      for (let i = 0; i < CEN.length; i++) {
        const v = d.dot(CEN[i]);
        if (v > v1) { v2 = v1; v1 = v; b = i; } else if (v > v2) v2 = v;
      }
      return { i: b, m: CEN.length > 1 ? v1 - v2 : 1 };
    };
    const total = projets.reduce((s, p) => s + p.neurones.length, 0) || 1;
    const minD2 = 0.007 * Math.min(1, 220 / total);
    const noeuds = [], aretes = [], parProjet = projets.map(() => []);
    const index = new Map();
    // 1. positions candidates dans chaque région (surface surtout, un peu de volume)
    projets.forEach((p, pj) => {
      const places = [];
      let essais = 0;
      while (places.length < p.neurones.length && essais++ < 60000) {
        const u = rnd() * 2 - 1, a = rnd() * 6.2832, s = Math.sqrt(1 - u * u);
        const d = new V3(s * Math.cos(a), u, s * Math.sin(a));
        const rg = region(d);
        if (rg.m < 0.07 || rg.i !== pj) continue;
        const rr = rnd() < 0.8 ? 0.93 + 0.07 * rnd() : 0.5 + 0.38 * rnd();
        const q = d.clone().multiplyScalar(rr * (1 + 0.025 * Math.sin(5 * a + 3 * u)));
        if (places.some((x) => x.distanceToSquared(q) < minD2 * (essais > 30000 ? 0.3 : 1))) continue;
        places.push(q);
      }
      while (places.length < p.neurones.length) places.push(CEN[pj].clone().multiplyScalar(0.9 + 0.05 * rnd()));
      // 2. on place les notes reliées près les unes des autres (parcours en largeur)
      const voisins = new Map(p.neurones.map((n) => [n.id, []]));
      p.synapses.forEach((s) => {
        if (voisins.has(s.a) && voisins.has(s.b)) { voisins.get(s.a).push([s.b, s.poids]); voisins.get(s.b).push([s.a, s.poids]); }
      });
      const libre = places.map(() => true), position = new Map();
      const ordre = p.neurones.slice().sort((x, y) => voisins.get(y.id).length - voisins.get(x.id).length);
      const prendre = (cible) => {
        let best = -1, bd = Infinity;
        places.forEach((q, i) => { if (libre[i]) { const d = q.distanceToSquared(cible); if (d < bd) { bd = d; best = i; } } });
        libre[best] = false;
        return places[best];
      };
      for (const depart of ordre) {
        if (position.has(depart.id)) continue;
        position.set(depart.id, prendre(CEN[pj].clone().multiplyScalar(0.95)));
        const file = [depart.id];
        while (file.length) {
          const x = file.shift();
          voisins.get(x).slice().sort((u, v) => v[1] - u[1]).forEach(([y]) => {
            if (position.has(y)) return;
            const c = new V3();
            let k = 0;
            voisins.get(y).forEach(([z]) => { if (position.has(z)) { c.add(position.get(z)); k++; } });
            position.set(y, prendre(c.multiplyScalar(1 / Math.max(1, k))));
            file.push(y);
          });
        }
      }
      p.neurones.forEach((n) => {
        const ix = noeuds.length;
        parProjet[pj].push(ix);
        index.set(pj + ':' + n.id, ix);
        noeuds.push({ p: position.get(n.id), proj: pj, id: n.id, titre: n.titre, validee: n.validee !== false,
          sensible: !!n.sensible, aretes: [], mode: 0, taille: 0.022 + rnd() * 0.014 });
      });
    });
    const N = noeuds.length;
    // 3. budget de points : neurones + poussière + synapses (≤ MAXP)
    const poussiere = Math.max(600, Math.min(2200, MAXP - N - 4000));
    const plans = [];
    const planifier = (pj, a, b, w, reve) => {
      const len = noeuds[a].p.distanceTo(noeuds[b].p);
      plans.push({ pj, a, b, w, reve, cnt: Math.max(9, Math.round(len * (34 + 50 * w) * (reve ? 1.5 : 1))) });
    };
    const vus = new Set();
    projets.forEach((p, pj) => {
      p.synapses.forEach((s) => {
        const a = index.get(pj + ':' + s.a), b = index.get(pj + ':' + s.b);
        if (a == null || b == null || a === b) return;
        const k = Math.min(a, b) + ':' + Math.max(a, b);
        if (vus.has(k)) return;
        vus.add(k);
        planifier(pj, a, b, Math.max(0.02, Math.min(1, s.poids)), false);
      });
    });
    // synapses de rêve : celles du dernier rêve, complétées par des paires éloignées (cachées)
    const paireEloignee = (pj) => {
      const ids = parProjet[pj];
      let best = null, bd = -1;
      for (let q = 0; q < 80 && ids.length > 1; q++) {
        const a = ids[Math.floor(rnd() * ids.length)], b = ids[Math.floor(rnd() * ids.length)];
        if (a === b || vus.has(Math.min(a, b) + ':' + Math.max(a, b))) continue;
        const d = noeuds[a].p.distanceTo(noeuds[b].p);
        if (d > bd) { bd = d; best = [a, b]; }
      }
      return best;
    };
    projets.forEach((p, pj) => {
      const paires = (p.reves || []).map((r) => [index.get(pj + ':' + r.a), index.get(pj + ':' + r.b)])
        .filter(([a, b]) => a != null && b != null && a !== b);
      while (paires.length < 5) { const x = paireEloignee(pj); if (!x) break; paires.push(x); }
      paires.slice(0, 5).forEach(([a, b]) => planifier(pj, a, b, 0.5, true));
    });
    const place = MAXP - N - poussiere;
    const somme = plans.reduce((s, x) => s + x.cnt, 0);
    const f = somme > place ? place / somme : 1;
    const G = creerGeometrie(MAXP), A = G.a;
    const dotNA = new Int32Array(MAXP).fill(-1), dotNB = new Int32Array(MAXP).fill(-1), dotE = new Int32Array(MAXP).fill(-1);
    let k = 0;
    noeuds.forEach((n, ix) => {
      const q = n.p;
      A.p0.set([q.x, q.y, q.z], k * 3); A.p1.set([q.x, q.y, q.z], k * 3); A.p2.set([q.x, q.y, q.z], k * 3);
      A.a.set([0, 0, n.taille, n.validee ? 1 : 0.55], k * 4); A.b.set([0, 0, 1, 0], k * 4); A.c.set([1, rnd()], k * 2);
      dotNA[k] = ix; dotNB[k] = ix; k++;
    });
    for (let i = 0; i < poussiere; i++) {
      const u = rnd() * 2 - 1, a = rnd() * 6.2832, s = Math.sqrt(1 - u * u);
      const volume = i >= poussiere * 0.83, rr = volume ? 0.35 + 0.6 * rnd() : 0.985 + 0.035 * rnd();
      A.p0.set([s * Math.cos(a) * rr, u * rr, s * Math.sin(a) * rr], k * 3);
      A.a.set([0, 0, 0.0048 + 0.0035 * rnd(), 0.12 + 0.3 * rnd()], k * 4);
      A.b.set([0, 0, volume ? 0.6 : 1, 0], k * 4); A.c.set([0, rnd()], k * 2); k++;
    }
    const ecrireCourbe = (e, a, b) => {
      const Aa = noeuds[a].p, Bb = noeuds[b].p, len = Aa.distanceTo(Bb);
      const mid = Aa.clone().add(Bb).multiplyScalar(0.5), nrm = mid.clone().normalize();
      const up = Math.abs(nrm.y) > 0.9 ? new V3(1, 0, 0) : new V3(0, 1, 0);
      const tan = new V3().crossVectors(nrm, up).normalize().applyAxisAngle(nrm, rnd() * 6.283);
      const ctrl = mid.clone().add(nrm.clone().multiplyScalar(0.02 + len * (0.10 + 0.24 * rnd()))).add(tan.multiplyScalar(len * (rnd() - 0.5) * 0.8));
      const cl = ctrl.length();
      if (cl > 1.12) ctrl.multiplyScalar(1.12 / cl);
      for (let q = e.debut; q < e.debut + e.nb; q++) {
        A.p0.set([Aa.x, Aa.y, Aa.z], q * 3); A.p1.set([ctrl.x, ctrl.y, ctrl.z], q * 3); A.p2.set([Bb.x, Bb.y, Bb.z], q * 3);
        dotNA[q] = a; dotNB[q] = b;
      }
      e.a = a; e.b = b;
    };
    plans.forEach((pl) => {
      const nb = Math.max(4, Math.round(pl.cnt * f));
      if (k + nb > MAXP) return;
      const e = { a: pl.a, b: pl.b, w: pl.w, proj: pl.pj, vivante: pl.reve ? 0 : 1, mode: pl.reve ? 2 : 0, debut: k, nb, reve: pl.reve };
      for (let q = 0; q < nb; q++, k++) {
        A.a.set([(q + 0.5) / nb, 0, 0.0098 + 0.0055 * pl.w, 0.42 + 0.58 * pl.w], k * 4);
        A.b.set([0, 0, e.vivante, e.mode], k * 4); A.c.set([2, rnd()], k * 2); dotE[k] = aretes.length;
      }
      ecrireCourbe(e, pl.a, pl.b);
      aretes.push(e);
      noeuds[pl.a].aretes.push(aretes.length - 1); noeuds[pl.b].aretes.push(aretes.length - 1);
    });
    G.g.setDrawRange(0, k);
    pts = new THREE.Points(G.g, matPoints);
    pts.frustumCulled = false;
    sph.add(pts);
    const RG = creerGeometrie(8);
    for (let i = 0; i < 8; i++) { RG.a.a.set([0, 0, 0.085, 1], i * 4); RG.a.b.set([0, 0, 0, 1], i * 4); RG.a.c.set([1, 0], i * 2); }
    anneaux = new THREE.Points(RG.g, matAnneaux);
    anneaux.frustumCulled = false;
    sph.add(anneaux);
    Object.assign(S, { noeuds, aretes, N, parProjet, projets, index, A, geo: G.g, total: k, dotNA, dotNB, dotE, RG,
      act: new Float32Array(N), eact: new Float32Array(aretes.length), useE: false, focus: -1, selection: -1, survol: -1,
      alertes: [], ecrireCourbe, CEN });
    rafraichirEtat();
    compter();
  }

  // ------------------------------------------------------------------
  // États (bleu / jaune / orange), activité, alertes
  // ------------------------------------------------------------------
  const focF = (pj) => (S.focus < 0 ? 1 : (S.focus === pj ? 1 : S.focDim));
  function rafraichirEtat() {
    const B = S.A.b;
    S.aretes.forEach((e) => {
      const z = e.vivante * focF(e.proj);
      for (let k = e.debut; k < e.debut + e.nb; k++) { B[k * 4 + 2] = z; B[k * 4 + 3] = e.mode; }
    });
    S.noeuds.forEach((n, ix) => { B[ix * 4 + 2] = focF(n.proj); B[ix * 4 + 3] = n.mode; });
    S.geo.attributes.aB.needsUpdate = true;
    if (S.demanderImage) S.demanderImage();
  }
  function pousserActivite() {
    const B = S.A.b, NA = S.dotNA, NB = S.dotNB, DE = S.dotE, ea = S.eact, act = S.act;
    for (let i = 0; i < S.total; i++) {
      const a = NA[i];
      if (a < 0) continue;
      if (S.useE && DE[i] >= 0) { B[i * 4] = B[i * 4 + 1] = ea[DE[i]]; } else { B[i * 4] = act[a]; B[i * 4 + 1] = act[NB[i]]; }
    }
    S.geo.attributes.aB.needsUpdate = true;
  }
  function compter() {
    const e = S.aretes.filter((x) => !x.reve && x.vivante > 0.5).length;
    if (options.auChangement) options.auChangement({ neurones: S.N, synapses: e, archivees: S.arch, projets: S.projets.length });
  }
  function rafraichirAnneaux() {
    const R = S.RG.a;
    let c = 0;
    for (let i = 0; i < 8; i++) R.b[i * 4 + 2] = 0;
    S.alertes.forEach((p) => p.noeuds.forEach((n) => {
      if (c >= 8) return;
      const P = S.noeuds[n].p;
      R.p0.set([P.x, P.y, P.z], c * 3); R.b[c * 4 + 2] = 1; R.b[c * 4 + 3] = 1; c++;
    }));
    S.RG.g.attributes.aP0.needsUpdate = true;
    S.RG.g.attributes.aB.needsUpdate = true;
  }
  /** Proposition en attente : anneaux jaunes sur ses notes, et lien jaune entre les deux premières. */
  function ajouterAlerte(prop) {
    const pj = S.projets.findIndex((p) => p.nom === prop.projet);
    if (pj < 0 || S.alertes.some((x) => x.cle === prop.projet + ':' + prop.id)) return;
    const noeuds = (prop.notes || []).map((id) => S.index.get(pj + ':' + id)).filter((x) => x != null).slice(0, 2);
    const al = { cle: prop.projet + ':' + prop.id, projet: prop.projet, id: prop.id, noeuds, arete: null };
    if (noeuds.length === 2) {
      const libre = S.aretes.findIndex((e) => e.reve && e.proj === pj && e.mode !== 1 && !S.alertes.some((x) => x.arete === S.aretes.indexOf(e)));
      if (libre >= 0) {
        const e = S.aretes[libre];
        if (!((e.a === noeuds[0] && e.b === noeuds[1]) || (e.a === noeuds[1] && e.b === noeuds[0]))) {
          S.ecrireCourbe(e, noeuds[0], noeuds[1]);
          ['aP0', 'aP1', 'aP2'].forEach((x) => { S.geo.attributes[x].needsUpdate = true; });
        }
        e.vivante = 1; e.mode = 1; al.arete = libre;
      }
    }
    noeuds.forEach((n) => { S.noeuds[n].mode = 1; });
    S.alertes.push(al);
    rafraichirAnneaux(); rafraichirEtat();
  }
  function retirerAlerte(projet, id) {
    const i = S.alertes.findIndex((x) => x.cle === projet + ':' + id);
    if (i < 0) return;
    const al = S.alertes[i];
    S.alertes.splice(i, 1);
    if (al.arete != null) { const e = S.aretes[al.arete]; e.vivante = 0; e.mode = 2; }
    al.noeuds.forEach((n) => { if (!S.alertes.some((x) => x.noeuds.includes(n))) S.noeuds[n].mode = 0; });
    rafraichirAnneaux(); rafraichirEtat();
  }
  /** Met les alertes en accord avec la liste des propositions en attente. */
  function synchroniserAlertes(liste) {
    const cles = new Set(liste.map((p) => p.projet + ':' + p.id));
    S.alertes.slice().forEach((a) => { if (!cles.has(a.cle)) retirerAlerte(a.projet, a.id); });
    liste.forEach(ajouterAlerte);
  }

  // ------------------------------------------------------------------
  // Caméra et interaction (glisser avec inertie, molette, pincement, clavier)
  // ------------------------------------------------------------------
  const vel = { x: 0, y: 0 }, pointeurs = {};
  let bouge = 0, t0 = 0, pincement0 = 0;
  const sourisSurvol = { x: 0, y: 0, actif: false };
  const fitD = () => Math.max(1.22 / (TH * 0.86), 1.22 / (TH * S.asp * 0.92));
  function redimensionner() {
    S.W = Math.max(2, conteneur.clientWidth); S.H = Math.max(2, conteneur.clientHeight); S.asp = S.W / S.H;
    renderer.setSize(S.W, S.H, false);
    camera.aspect = S.asp; camera.updateProjectionMatrix();
    S.D = fitD();
    U.uK.value = S.H * renderer.getPixelRatio() / (2 * TH);
    (S.auRedimensionnement || []).forEach((f) => f());
    if (S.demanderImage) S.demanderImage();
  }
  if (window.ResizeObserver) new ResizeObserver(redimensionner).observe(conteneur);
  else window.addEventListener('resize', redimensionner);
  redimensionner();
  const relancer = () => demanderImage();
  cv.addEventListener('pointerdown', (e) => {
    cv.setPointerCapture(e.pointerId);
    pointeurs[e.pointerId] = { x: e.clientX, y: e.clientY };
    const ks = Object.keys(pointeurs);
    if (ks.length === 1) { bouge = 0; t0 = performance.now(); S.glisse = true; vel.x = vel.y = 0; }
    if (ks.length === 2) pincement0 = Math.hypot(pointeurs[ks[0]].x - pointeurs[ks[1]].x, pointeurs[ks[0]].y - pointeurs[ks[1]].y);
    relancer();
  });
  cv.addEventListener('pointermove', (e) => {
    const p = pointeurs[e.pointerId];
    if (!p) {
      if (e.pointerType === 'mouse') { const r = cv.getBoundingClientRect(); sourisSurvol.x = e.clientX - r.left; sourisSurvol.y = e.clientY - r.top; sourisSurvol.actif = true; demanderImage(); }
      return;
    }
    const ks = Object.keys(pointeurs);
    if (ks.length === 1) {
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      bouge += Math.abs(dx) + Math.abs(dy);
      sph.rotation.y += dx * 0.006; sph.rotation.x = Math.max(-1.1, Math.min(1.1, sph.rotation.x + dy * 0.006));
      vel.y = dx * 0.006; vel.x = dy * 0.006;
    } else if (ks.length === 2) {
      pointeurs[e.pointerId] = { x: e.clientX, y: e.clientY };
      const d = Math.hypot(pointeurs[ks[0]].x - pointeurs[ks[1]].x, pointeurs[ks[0]].y - pointeurs[ks[1]].y);
      if (pincement0 > 0) S.zoom = Math.max(0.7, Math.min(1.5, S.zoom * pincement0 / d));
      pincement0 = d; bouge += 10;
    }
    pointeurs[e.pointerId] = { x: e.clientX, y: e.clientY };
    relancer();
  });
  cv.addEventListener('pointerup', (e) => {
    const avait = !!pointeurs[e.pointerId];
    delete pointeurs[e.pointerId];
    if (avait && Object.keys(pointeurs).length === 0) {
      S.glisse = false;
      if (bouge < 8 && performance.now() - t0 < 600) { const r = cv.getBoundingClientRect(); choisirA(e.clientX - r.left, e.clientY - r.top); }
    }
    pincement0 = 0;
    demanderImage();
  });
  cv.addEventListener('pointercancel', (e) => { delete pointeurs[e.pointerId]; S.glisse = false; demanderImage(); });
  cv.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && !pointeurs[e.pointerId]) { sourisSurvol.actif = false; survoler(-1); demanderImage(); } });
  cv.addEventListener('wheel', (e) => { e.preventDefault(); S.zoom = Math.max(0.7, Math.min(1.5, S.zoom * Math.exp(e.deltaY * 0.001))); relancer(); }, { passive: false });
  cv.addEventListener('keydown', (e) => {
    let ok = true;
    if (e.key === 'ArrowLeft') sph.rotation.y -= 0.15;
    else if (e.key === 'ArrowRight') sph.rotation.y += 0.15;
    else if (e.key === 'ArrowUp') sph.rotation.x = Math.max(-1.1, sph.rotation.x - 0.12);
    else if (e.key === 'ArrowDown') sph.rotation.x = Math.min(1.1, sph.rotation.x + 0.12);
    else if (e.key === '+' || e.key === '=') S.zoom = Math.max(0.7, S.zoom - 0.08);
    else if (e.key === '-') S.zoom = Math.min(1.5, S.zoom + 0.08);
    else if (e.key === 'Enter') { majEcran(); selectionner(plusProche(S.W / 2, S.H / 2, 1e5)); }
    else if (e.key === 'Escape' && S.selection >= 0) selectionner(-1);
    else ok = false;
    if (ok) { e.preventDefault(); relancer(); }
  });

  const _v = new V3();
  function majEcran() {
    sph.updateMatrixWorld();
    for (let i = 0; i < S.N; i++) {
      _v.copy(S.noeuds[i].p).applyMatrix4(sph.matrixWorld);
      const o = S.ecran[i] || (S.ecran[i] = {});
      o.wz = _v.z - sph.position.z;
      _v.project(camera);
      o.x = (_v.x * 0.5 + 0.5) * S.W; o.y = (-_v.y * 0.5 + 0.5) * S.H; o.ok = _v.z > -1 && _v.z < 1;
    }
  }
  function plusProche(x, y, seuil) {
    let best = -1, bd = seuil * seuil;
    for (let i = 0; i < S.N; i++) {
      if (S.focus >= 0 && S.noeuds[i].proj !== S.focus) continue;
      const q = S.ecran[i];
      if (!q || !q.ok || q.wz < -0.05 * sph.scale.x) continue;      // pas les neurones de l'autre face
      const d = (q.x - x) ** 2 + (q.y - y) ** 2;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }
  function survoler(i) {
    if (S.survol === i) return;
    S.survol = i;
    if (i < 0) cv.style.cursor = '';
  }
  function selectionner(i) {
    S.selection = i;
    if (S.demanderImage) S.demanderImage();
    if (i < 0) { anneau.hidden = true; return; }
    if (options.annoncer) options.annoncer(descrire(i).texte);
  }
  function choisirA(x, y) {
    majEcran();
    const tactile = window.matchMedia && window.matchMedia('(pointer:coarse)').matches;
    const i = plusProche(x, y, tactile ? 26 : 18);
    selectionner(i === S.selection ? -1 : i);
  }
  function descrire(i) {
    const n = S.noeuds[i];
    const liens = n.aretes.filter((k) => S.aretes[k].vivante > 0.5 && !S.aretes[k].reve).length;
    const etat = n.mode === 1 ? 'à valider' : (S.act[i] > 0.3 ? 'actif' : 'passif');
    return { titre: n.titre, projet: S.projets[n.proj].nom, liens, etat,
      texte: `${n.titre} · ${S.projets[n.proj].nom} · ${liens} lien${liens > 1 ? 's' : ''} · ${etat}` };
  }
  /** Allume une note (clic sur une note retenue) : la sphère tourne vers elle et la sélectionne. */
  function allumer(projet, id) {
    const pj = S.projets.findIndex((p) => p.nom === projet);
    const i = S.index.get(pj + ':' + id);
    if (i == null) return false;
    const P = S.noeuds[i].p;
    S.cibleY = Math.atan2(-P.x, P.z);
    S.cibleX = Math.max(-1.1, Math.min(1.1, Math.atan2(P.y, Math.hypot(P.x, P.z)) * 0.8));
    S.act[i] = 1; S.actSale = true; S.allume = { i, t: 2.5 };
    selectionner(i);
    return true;
  }

  // ------------------------------------------------------------------
  // Boucle d'animation
  // ------------------------------------------------------------------
  const vague = installerVague(S, { rafraichirEtat, pousserActivite, majEcran });
  const nuit = installerNuit(S, { rafraichirEtat, pousserActivite, compter, ajouterAlerte });
  let dernier = performance.now(), ema = 0.016, prCourant = DPR, prevu = false, apresPause = true;
  const ANG = { cible: null };

  /** Demande une image (une seule à la fois). Appelé par toute interaction ou animation. */
  function demanderImage() {
    if (prevu) return;
    prevu = true;
    requestAnimationFrame(boucle);
  }
  S.demanderImage = demanderImage;

  /** Faut-il encore dessiner l'image suivante ? (sinon : image fixe, plus rien ne tourne) */
  function encoreActif() {
    return S.glisse || Math.abs(vel.x) > 1e-4 || Math.abs(vel.y) > 1e-4 || S.cibleY != null
      || !!(S.vague || S.nuitS || S.allume) || S.impulsions.length > 0 || S.vif > 0.003
      || Math.abs((S.compactActif ? S.modeT : 0) - S.mode) > 0.002 || Math.abs(S.ecouteCible - S.ecoute) > 0.002
      || S.besoins.some((f) => f());
  }

  /** Impulsion de parole : part de la zone du projet concerné (4 au plus en même temps). */
  function impulsion(force, projet) {
    const pj = S.projets.findIndex((p) => p.nom === projet);
    const d = pj >= 0 && S.CEN && S.CEN[pj] ? S.CEN[pj] : new V3(0, 0.9, 0.45).normalize();
    S.impulsions.push({ d, age: 0, force });
    if (S.impulsions.length > 4) S.impulsions.shift();
    demanderImage();
  }

  function boucle(maintenant) {
    prevu = false;
    const dt = apresPause ? 1 / 60 : Math.min(0.05, (maintenant - dernier) / 1000);
    dernier = maintenant;
    U.uTime.value = maintenant / 1000;
    // écoute (champ de saisie actif) et intensité de parole (source unique)
    S.ecoute += (S.ecouteCible - S.ecoute) * Math.min(1, dt * 4);
    if (Math.abs(S.ecouteCible - S.ecoute) < 0.002) S.ecoute = S.ecouteCible;
    U.uListen.value = reduit ? 0 : S.ecoute;
    const voix = S.parole ? S.parole.valeur : 0;
    S.vif += ((S.parole && S.parole.parle ? Math.max(0.55, voix) : voix) - S.vif) * Math.min(1, dt * 5);
    if (S.vif < 0.003 && !(S.parole && S.parole.parle)) S.vif = 0;
    U.uVif.value = S.vif;
    S.impulsions = S.impulsions.filter((x) => (x.age += dt) < 1.6);
    for (let i = 0; i < 4; i++) {
      const x = S.impulsions[i];
      if (x) { U.uPI.value[i].set(x.d.x, x.d.y, x.d.z, x.age); U.uPF.value[i] = x.force; }
      else { U.uPI.value[i].w = -1; U.uPF.value[i] = 0; }
    }
    // repli automatique si l'image ralentit (objectif 60 images/s) — mesuré seulement en animation
    if (!apresPause) {
      ema += (dt - ema) * 0.05;
      if (ema > 0.034 && prCourant > 1) { prCourant = Math.max(1, prCourant - 0.25); DPR = prCourant; renderer.setPixelRatio(prCourant); redimensionner(); ema = 0.016; }
      else if (ema > 0.05 && prCourant <= 1 && U.uPous.value > 0) { U.uPous.value = 0; ema = 0.016; S.allege = true; }
    }
    apresPause = false;
    // rotation : inertie après un glisser, ou rotation vers une note allumée (jamais automatique)
    if (S.cibleY != null && !S.glisse) {
      let df = S.cibleY - sph.rotation.y; df = Math.atan2(Math.sin(df), Math.cos(df));
      sph.rotation.y += df * Math.min(1, dt * 3); sph.rotation.x += (S.cibleX - sph.rotation.x) * Math.min(1, dt * 3);
      if (Math.abs(df) < 0.01) S.cibleY = null;
    } else if (!S.glisse) {
      sph.rotation.y += vel.y; sph.rotation.x = Math.max(-1.1, Math.min(1.1, sph.rotation.x + vel.x));
      vel.x *= 0.92; vel.y *= 0.92;
      if (Math.abs(vel.x) < 1e-4) vel.x = 0;
      if (Math.abs(vel.y) < 1e-4) vel.y = 0;
    }
    // mode compact quand un hologramme est affiché
    const cibleMode = S.compactActif ? S.modeT : 0;
    S.mode += (cibleMode - S.mode) * Math.min(1, dt * 4);
    if (Math.abs(cibleMode - S.mode) < 0.002) S.mode = cibleMode;
    const m = S.mode, Dz = S.D * S.zoom;
    camera.position.set(0, 0, Dz); camera.lookAt(0, 0, 0);
    sph.scale.setScalar(1 - 0.58 * m); U.uScl.value = 1 - 0.58 * m; sph.position.y = m * 0.60 * Dz * TH;
    U.uCam.value = Dz; U.uGlobal.value = 1 - 0.05 * m;
    // vague, nuit, note allumée, activité
    vague.etape(dt); nuit.etape(dt, maintenant);
    if (S.allume && !S.vague && !S.nuitS) {
      S.allume.t -= dt;
      S.act[S.allume.i] = Math.max(0, Math.min(1, S.allume.t));
      if (S.allume.t <= 0) { S.act[S.allume.i] = 0; S.allume = null; }
      S.actSale = true;
    }
    if (S.actSale) { pousserActivite(); if (!S.vague && !S.nuitS && !S.allume) S.actSale = false; }
    S.etapes.forEach((f) => f(dt, maintenant));
    // survol, sélection, étiquettes
    majEcran(); vague.placerEtiquettes();
    if (sourisSurvol.actif && !S.glisse) { const hi = plusProche(sourisSurvol.x, sourisSurvol.y, 16); survoler(hi); cv.style.cursor = hi >= 0 ? 'pointer' : ''; }
    const si = S.selection;
    if (si >= 0) { const q = S.ecran[si]; anneau.hidden = !(q && q.ok); if (q) { anneau.style.left = q.x + 'px'; anneau.style.top = q.y + 'px'; } } else anneau.hidden = true;
    const montre = S.survol >= 0 && S.survol !== si ? S.survol : (si >= 0 ? si : -1);
    if (montre >= 0 && S.ecran[montre]) {
      const h = S.ecran[montre], d = descrire(montre);
      bulle.hidden = false; bulle.style.left = h.x + 'px'; bulle.style.top = h.y + 'px';
      const cle = montre + ':' + d.etat + ':' + d.liens;
      if (bulle.dataset.cle !== cle) {
        bulle.dataset.cle = cle; bulle.textContent = '';
        bulle.appendChild(document.createTextNode(d.titre));
        bulle.appendChild(el('small', '', `${d.projet} · ${d.liens} lien${d.liens > 1 ? 's' : ''} · ${d.etat}`));
      }
    } else { bulle.hidden = true; bulle.dataset.cle = ''; }
    renderer.render(scene, camera);
    S.images = (S.images || 0) + 1;
    if (encoreActif()) demanderImage();
    else apresPause = true;              // image fixe : plus rien n'est recalculé ni redessiné
  }

  const api = {
    S, charger, ajouterAlerte, retirerAlerte, synchroniserAlertes, allumer, selectionner, redimensionner,
    demanderImage,
    /** Vague de recherche (4 temps). Renvoie une poignée : fournir(traces), fin (promesse). */
    rechercher: (projet) => { const v = vague.rechercher(projet); demanderImage(); return v; },
    /** Vague seule (3 s) avant un hologramme qui n'est pas une recherche. */
    balayer: () => { const v = vague.balayer(); demanderImage(); return v; },
    /** Nuit en 4 phases à partir d'un bilan déjà calculé. */
    nuit: (bilan) => { const v = nuit.lancer(bilan); demanderImage(); return v; },
    occupee: () => !!(S.vague || S.nuitS),
    /** Branche la source unique d'intensité de parole (voir parole.js). */
    brancherParole(parole) {
      S.parole = parole;
      parole.abonner((e) => {
        if (e.type === 'impulsion') impulsion(e.force, e.origine);
        else demanderImage();
      });
    },
    ecouter(oui) { S.ecouteCible = oui ? 1 : 0; demanderImage(); },
    /** Mode compact : la sphère rapetisse et monte quand un hologramme est ouvert. */
    compacter(actif, cible = 1) { S.compactActif = actif; S.modeT = cible; demanderImage(); },
    pointEcran(x, y, z = 1.0) { // conversion px -> monde à la profondeur des hologrammes
      const dist = S.D * S.zoom - z, hh = dist * TH, hw = hh * S.asp;
      return { x: (x / S.W * 2 - 1) * hw, y: (1 - y / S.H * 2) * hh, hw, hh };
    },
    projetIndex: (nom) => S.projets.findIndex((p) => p.nom === nom),
  };
  demanderImage();
  return api;
}
