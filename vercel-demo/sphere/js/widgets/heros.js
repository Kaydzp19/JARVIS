// Objets 3D des hologrammes : fil de fer lumineux qui tourne (puce, soleil et nuage
// avec pluie, cadenas, barres 3D). Kayd peut les faire tourner et zoomer à la main.

import * as THREE from 'three';
import { sm } from '../outils.js';

const lmat = (c) => new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
function aretesDe(geo, couleur, mats) {
  const l = new THREE.LineSegments(new THREE.EdgesGeometry(geo), lmat(couleur));
  mats.push(l.material);
  return l;
}

function puce(vivant) {
  const g = new THREE.Group(), mats = [];
  g.add(aretesDe(new THREE.BoxGeometry(1, 0.16, 1), 0x6FD7FF, mats));
  const coeur = aretesDe(new THREE.BoxGeometry(0.56, 0.22, 0.56), 0x4CC9FF, mats);
  g.add(coeur);
  const pts = [];
  for (let i = 0; i < 8; i++) {
    const o = -0.4 + i * 0.115;
    pts.push(o, 0, 0.5, o, 0, 0.66, o, 0, -0.5, o, 0, -0.66, 0.5, 0, o, 0.66, 0, o, -0.5, 0, o, -0.66, 0, o);
  }
  const pg = new THREE.BufferGeometry();
  pg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pts), 3));
  const pl = new THREE.LineSegments(pg, lmat(0x4CC9FF)); mats.push(pl.material); g.add(pl);
  g.userData = { mats, tick(t) { g.rotation.y = t * 0.5; g.rotation.x = 0.55; const s = 1 + 0.06 * Math.sin(t * 3) * ((vivant() || 30) / 60); coeur.scale.set(s, s, s); } };
  return g;
}

function meteo(pluie) {
  const g = new THREE.Group(), mats = [];
  const soleil = aretesDe(new THREE.IcosahedronGeometry(0.28, 1), 0xFFD84A, mats);
  soleil.position.set(0.22, 0.18, 0); g.add(soleil);
  [[-0.15, -0.08, 0.3], [0.12, -0.12, 0.24], [-0.32, -0.14, 0.2]].forEach((q) => {
    const n = aretesDe(new THREE.IcosahedronGeometry(q[2], 1), 0x6FD7FF, mats);
    n.position.set(q[0], q[1], 0.1); g.add(n);
  });
  const nb = pluie ? 14 : 0, rp = new Float32Array(Math.max(1, nb) * 3);
  for (let i = 0; i < nb; i++) { rp[i * 3] = -0.45 + Math.random() * 0.7; rp[i * 3 + 1] = -0.3 - Math.random() * 0.3; rp[i * 3 + 2] = 0.1; }
  const rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.BufferAttribute(rp, 3));
  const rm = new THREE.PointsMaterial({ color: 0x8fdcff, size: 0.035, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  g.add(new THREE.Points(rg, rm));
  g.userData = { mats, extra: [rm], tick(t) {
    g.rotation.y = Math.sin(t * 0.6) * 0.5; soleil.rotation.y = t * 0.7;
    const a = rg.attributes.position.array;
    for (let q = 0; q < nb; q++) { a[q * 3 + 1] -= 0.006; if (a[q * 3 + 1] < -0.62) a[q * 3 + 1] = -0.3; }
    rg.attributes.position.needsUpdate = true;
  } };
  return g;
}

function cadenas() {
  const g = new THREE.Group(), mats = [];
  g.add(aretesDe(new THREE.BoxGeometry(0.7, 0.5, 0.4), 0xFFD84A, mats));
  const anse = aretesDe(new THREE.TorusGeometry(0.2, 0.025, 6, 16, Math.PI), 0xFFD84A, mats);
  anse.position.y = 0.25; g.add(anse);
  g.userData = { mats, tick(t) { g.rotation.y = Math.sin(t * 0.8) * 0.7; g.rotation.x = 0.25; } };
  return g;
}

function barres(valeurs, max, w, h, incline, couleurs) {
  const g = new THREE.Group(), mats = [], liste = [], n = valeurs.length, pas = w / Math.max(1, n), bw = pas * 0.46;
  valeurs.forEach((v, i) => {
    const box = new THREE.BoxGeometry(1, 1, 1); box.translate(0, 0.5, 0);
    const support = new THREE.Group(); support.position.set(-w / 2 + pas * (i + 0.5), -h / 2, 0);
    const coul = (couleurs && couleurs[i]) || (i === n - 1 ? 0xFFFFFF : 0x4CC9FF);
    const m = new THREE.Mesh(box, new THREE.MeshBasicMaterial({ color: coul, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    const ln = new THREE.LineSegments(new THREE.EdgesGeometry(box), lmat(coul === 0x4CC9FF ? 0x8FE0FF : coul));
    support.add(m); support.add(ln); support.scale.set(bw, 0.001, bw); g.add(support);
    liste.push({ s: support, h: Math.max(0.03, (v || 0) / (max || 1)) * h });
    mats.push(m.material, ln.material);
  });
  g.userData = { mats, remplir: true, tick(t, prog) {
    g.rotation.x = incline ? -0.38 : -0.2; g.rotation.y = Math.sin(t * 0.5) * 0.12;
    const e = sm(0.15, 0.95, prog);
    liste.forEach((b, i) => { b.s.scale.y = Math.max(0.001, b.h * sm(0.05 * i, 0.5 + 0.05 * i, e)); });
  } };
  return g;
}

/**
 * Construit l'objet décrit par la scène : { type, x, y, w, h, ... } en pixels du widget.
 * f = taille d'un pixel du widget dans le monde 3D. Renvoie le groupe positionné.
 */
export function construireHeros(d, f, Wd, Hd, vivant) {
  const sx = d.w * f, sy = d.h * f;
  let g;
  if (d.type === 'puce') { g = puce(vivant); g.scale.setScalar(Math.min(sx, sy) * 0.62); }
  else if (d.type === 'meteo') { g = meteo(d.pluie); g.scale.setScalar(Math.min(sx, sy) * 1.5); }
  else if (d.type === 'cadenas') { g = cadenas(); g.scale.setScalar(Math.min(sx, sy) * 0.9); }
  else if (d.type === 'barres') {
    const max = Math.max(1e-9, d.max || Math.max(...d.valeurs));
    g = barres(d.valeurs, max * (d.incline ? 1.05 : 1), sx * 0.9, sy * (d.incline ? 0.92 : 0.85), !!d.incline, d.couleurs);
  } else return null;
  const conteneur = new THREE.Group();
  conteneur.add(g);
  conteneur.position.set(((d.x + d.w / 2) - Wd / 2) * f, (Hd / 2 - (d.y + d.h / 2)) * f, 0.05);
  conteneur.userData = { objet: g, base: g.scale.x, rotation: { x: 0, y: 0 }, zoom: 1 };
  return conteneur;
}

export function liberer(objet) {
  objet.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
}
