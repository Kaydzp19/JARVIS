// La vague d'activation orange (partie active de JARVIS), environ 10 secondes :
//   T1 NOTATION     0 – 2,7 s  un front courbe traverse TOUTE la sphère depuis le côté du projet
//                              interrogé ; le compteur de neurones notés monte (calcul par code).
//   T2 PROPAGATION  1,9 – 5 s  depuis 3 graines, le long des synapses, selon leur poids ;
//                              les chemins vers les notes gardées restent allumés.
//   T3 SÉLECTION    5,2 – 8,6 s le reste s'éteint, la zone gardée se tourne vers l'écran ;
//                              seules les notes gardées (grandes), les notes de passage (petites)
//                              et les synapses utilisées restent orange, avec leur titre numéroté.
//   T4 RÉPONSE      8,6 – 9,8 s retour au bleu ; JARVIS répond.
// Le minutage ne dépend pas du calcul : la trace (identifiants, scores, liens) arrive du
// serveur pendant la vague ; si elle tarde, la vague attend au début de la propagation.

import { el, sm } from './outils.js';

export const TEMPS = { VAGUE: 2.7, P0: 1.9, P1: 5.0, SEL: 5.2, TENUE: 8.6, FIN: 9.8, BALAYAGE: 3.2, ATTENTE_MAX: 20 };

export function installerVague(S, f) {
  const { THREE, U, sph, camera } = S;
  const _o = new THREE.Vector3();
  const phase = (t) => { if (S.ecrirePhase) S.ecrirePhase(t); };

  function eteindre() { U.uWR.value = -9; U.uWAmp.value = 0; U.uDim.value = 0; }

  function terminer() {
    for (let i = 0; i < S.N; i++) S.act[i] = 0;
    S.eact.fill(0); S.useE = false; f.pousserActivite(); S.actSale = false; eteindre();
    if (S.vague && S.vague.etq) S.vague.etq.forEach((l) => l.el.remove());
    phase('');
    const fin = S.vague && S.vague.resoudreFin;
    S.vague = null;
    if (S.focus >= 0) { S.focus = -1; f.rafraichirEtat(); }
    if (fin) fin();
  }

  function origine(projet) {
    const pj = S.projets.findIndex((p) => p.nom === projet);
    return pj >= 0 && S.CEN[pj] ? S.CEN[pj].clone() : new THREE.Vector3(0, 0.9, 0.45).normalize();
  }

  function balayer() {
    if (S.vague || S.nuitS) return Promise.resolve();
    return new Promise((resolve) => {
      S.vague = { t: 0, tf: 0, balayage: true, resoudreFin: resolve, org: new THREE.Vector3(Math.random() * 2 - 1, 0.7, Math.random() * 2 - 1).normalize() };
      phase('1 · BALAYAGE · tous les neurones et synapses');
    });
  }

  /** Prépare la propagation à partir des traces (une par projet interrogé). */
  function preparer(V, traces) {
    V.notees = 0;
    traces.forEach((trace) => {
      const pj = S.projets.findIndex((p) => p.nom === trace.projet);
      if (pj < 0) return;
      const idx = (id) => S.index.get(pj + ':' + id);
      const ids = S.parProjet[pj];
      const graines = trace.graines.map(idx).filter((x) => x != null);
      const dist = new Map(ids.map((i) => [i, Infinity]));
      graines.forEach((g) => dist.set(g, 0));
      const fait = new Set();
      for (;;) {
        let u = -1, bd = Infinity;
        ids.forEach((i) => { if (!fait.has(i) && dist.get(i) < bd) { bd = dist.get(i); u = i; } });
        if (u < 0) break;
        fait.add(u);
        S.noeuds[u].aretes.forEach((k) => {
          const e = S.aretes[k];
          if (e.vivante < 0.5 || e.reve) return;
          const v = e.a === u ? e.b : e.a, nd = bd + 1 / (0.12 + e.w);
          if (nd < dist.get(v)) dist.set(v, nd);
        });
      }
      let maxD = 1;
      ids.forEach((i) => { const d = dist.get(i); if (d < Infinity && d > maxD) maxD = d; });
      const dn = (i) => (dist.get(i) === Infinity ? maxD : dist.get(i));
      ids.forEach((i) => { V.nT.set(i, TEMPS.P0 + (TEMPS.P1 - TEMPS.P0) * dn(i) / maxD); V.ids.push(i); });
      ids.forEach((i) => S.noeuds[i].aretes.forEach((k) => {
        const e = S.aretes[k];
        if (e.reve || e.vivante < 0.5 || V.eT.has(k)) return;
        V.eT.set(k, TEMPS.P0 + (TEMPS.P1 - TEMPS.P0) * Math.min(dn(e.a), dn(e.b)) / maxD);
        V.eids.push(k);
      }));
      trace.retenues.forEach((r) => {
        const i = idx(r.id);
        if (i == null) return;
        V.gardees.add(i); V.utilises.set(i, 2);
        V.liste.push({ i, titre: r.titre, score: r.score, rang: V.liste.length + 1 });
      });
      (trace.intermediaires || []).map(idx).forEach((i) => { if (i != null && !V.utilises.has(i)) V.utilises.set(i, 1); });
      (trace.synapses || []).forEach((s) => {
        const a = idx(s.a), b = idx(s.b);
        if (a == null || b == null) return;
        const k = S.noeuds[a].aretes.find((x) => { const e = S.aretes[x]; return (e.a === a && e.b === b) || (e.a === b && e.b === a); });
        if (k != null) V.aretesUtilisees.add(k);
      });
      V.notees += trace.notees || ids.length;
    });
    V.eids.forEach((k) => { const e = S.aretes[k]; if (V.gardees.has(e.a) && V.gardees.has(e.b)) V.aretesUtilisees.add(k); });
    V.pret = true;
  }

  function rechercher(projet) {
    if (S.vague || S.nuitS) return null;
    const pj = projet === '*' ? -1 : S.projets.findIndex((p) => p.nom === projet);
    const enCours = projet === '*' ? S.parProjet.flat() : (S.parProjet[pj] || []);
    let resoudreReponse, resoudreFin;
    const V = {
      t: 0, tf: 0, projet, pret: false, attente: 0, aNoter: enCours.length || S.N, notees: 0,
      nT: new Map(), eT: new Map(), ids: [], eids: [], gardees: new Set(), utilises: new Map(), aretesUtilisees: new Set(),
      liste: [], etq: null, reponseFaite: false, org: origine(projet),
    };
    const poignee = {
      reponse: new Promise((r) => { resoudreReponse = r; }),
      fin: new Promise((r) => { resoudreFin = r; }),
      fournir(traces) { if (S.vague === V && !V.pret) preparer(V, traces); },
      annuler() { if (S.vague === V) terminer(); },
    };
    V.resoudreReponse = resoudreReponse; V.resoudreFin = resoudreFin;
    S.focus = pj; S.focDim = 0.4; S.useE = true; S.eact.fill(0); f.rafraichirEtat();
    S.vague = V;
    phase('1 · NOTATION · 0 neurones notés');
    return poignee;
  }

  function etape(dt) {
    const V = S.vague;
    if (!V) return;
    V.tf += dt;
    // la vague attend la trace au début de la propagation (le calcul ne dicte pas le rythme)
    if (!V.balayage && !V.pret && V.t + dt >= TEMPS.P0) {
      V.attente += dt;
      if (V.attente > TEMPS.ATTENTE_MAX) { if (V.resoudreReponse) V.resoudreReponse(null); terminer(); return; }
    } else V.t += dt;
    const tau = V.t, u = Math.min(1.12, V.tf / TEMPS.VAGUE), uc = Math.min(1, u);
    const front = -1.35 + 2.6 * (uc * uc * (3 - 2 * uc));
    if (!V.dir) {
      _o.copy(V.org).applyMatrix4(sph.matrixWorld).applyMatrix4(camera.matrixWorldInverse);
      const ol = Math.hypot(_o.x, _o.y);
      V.dir = ol < 0.18 ? new THREE.Vector3(0.85, 0.5, 0).normalize() : new THREE.Vector3(-_o.x / ol, -_o.y / ol, 0);
    }
    U.uWD.value.copy(V.dir); U.uWR.value = u < 1.1 ? front : -9;
    U.uWAmp.value = 0.95 * sm(0, 0.06, u) * (1 - sm(0.92, 1.1, u));
    if (V.balayage) { if (V.tf >= TEMPS.BALAYAGE) terminer(); return; }
    const selR = sm(TEMPS.SEL, TEMPS.SEL + 0.8, tau), fondu = 1 - sm(TEMPS.TENUE, TEMPS.FIN, tau);
    // la zone des notes gardées se tourne face à l'écran
    if (V.pret && V.faceY == null) {
      let cx = 0, cz = 0;
      V.liste.forEach((x) => { const P = S.noeuds[x.i].p; cx += P.x; cz += P.z; });
      const n = V.liste.length;
      V.faceY = n && Math.hypot(cx, cz) / n > 0.3 ? Math.atan2(-cx, cz) : false;
    }
    if (V.faceY !== false && V.faceY != null && tau > TEMPS.SEL - 1.6 && !S.glisse) {
      let df = V.faceY - sph.rotation.y; df = Math.atan2(Math.sin(df), Math.cos(df));
      sph.rotation.y += df * Math.min(1, dt * 2.4);
    }
    for (let i = 0; i < S.N; i++) S.act[i] = 0;
    V.ids.forEach((n) => {
      const d = tau - V.nT.get(n), us = V.utilises.get(n) || 0;
      let a = d > 0 ? 0.38 * Math.exp(-d * 2.4) * (1 - selR) : 0;
      if (us) { a = Math.max(a, sm(0, 0.45, d) * 0.6); a = Math.max(a, us === 2 ? selR : selR * 0.78); }
      S.act[n] = a * fondu;
    });
    V.eids.forEach((k) => {
      const d = tau - V.eT.get(k);
      let a = d > 0 ? 0.36 * Math.exp(-d * 2.2) * (1 - selR) : 0;
      if (V.aretesUtilisees.has(k)) a = Math.max(a, sm(0, 0.5, d) * 0.68, selR * 0.95);
      S.eact[k] = a * fondu;
    });
    U.uDim.value = 0.42 * sm(TEMPS.SEL - 0.7, TEMPS.SEL + 0.7, tau) * fondu;
    if (!V.etq && V.pret && tau >= TEMPS.SEL - 0.1) {
      V.etq = V.liste.map((x, rk) => {
        const d = el('div', 'etq');
        d.appendChild(el('b', '', (rk < 9 ? '0' : '') + (rk + 1)));
        d.appendChild(document.createTextNode(x.titre));
        S.etiquettes.appendChild(d);
        return { el: d, i: x.i, rk, a: 0 };
      });
    }
    if (V.etq) V.etq.forEach((l) => { l.a = sm(TEMPS.SEL + 0.14 * l.rk + 0.2, TEMPS.SEL + 0.14 * l.rk + 0.7, tau) * (1 - sm(TEMPS.TENUE - 0.3, TEMPS.TENUE + 0.5, tau)); });
    const nUtil = V.aretesUtilisees.size;
    const compte = Math.round(V.aNoter * uc);
    phase(V.tf < TEMPS.VAGUE ? `1 · NOTATION · ${compte} neurones notés`
      : !V.pret ? `1 · NOTATION · ${V.aNoter} neurones notés · calcul…`
        : tau < TEMPS.SEL ? '2 · PROPAGATION par les synapses'
          : tau < TEMPS.TENUE ? `3 · SÉLECTION · ${V.liste.length} notes · ${nUtil} liens utilisés` : '4 · RÉPONSE');
    S.actSale = true;
    if (tau >= TEMPS.TENUE && !V.reponseFaite) {
      V.reponseFaite = true;
      V.resoudreReponse({ notees: V.notees, retenues: V.liste, liens: nUtil });
    }
    if (tau >= TEMPS.FIN) terminer();
  }

  /** Étiquettes : titres seulement, numérotées, sans chevauchement, cachées derrière la sphère. */
  function placerEtiquettes() {
    const V = S.vague;
    if (!V || !V.etq) return;
    const items = [], sc = sph.scale.x || 1, mx = Math.max(80, S.W - (S.W < 560 ? 130 : 190));
    const pas = S.W < 560 ? 18 : 21;
    V.etq.forEach((l) => {
      const q = S.ecran[l.i];
      if (!q || !q.ok) { l.el.style.opacity = 0; return; }
      const face = Math.max(0, Math.min(1, (q.wz / sc + 0.12) / 0.35)), op = l.a * face;
      l.el.style.opacity = op.toFixed(3);
      if (op < 0.01) return;
      items.push({ l, x: Math.max(4, Math.min(mx, q.x + 14)), y: Math.max(4, q.y - 22) });
    });
    items.sort((a, b) => a.y - b.y);
    for (let j = 1; j < items.length; j++) for (let m = 0; m < j; m++) {
      if (Math.abs(items[j].x - items[m].x) < 160 && Math.abs(items[j].y - items[m].y) < pas) items[j].y = items[m].y + pas;
    }
    items.forEach((it) => { it.l.el.style.transform = `translate(${Math.round(it.x)}px,${Math.round(it.y)}px)`; });
  }

  return { rechercher, balayer, etape, placerEtiquettes, terminer };
}
