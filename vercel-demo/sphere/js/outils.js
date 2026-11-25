// Petits outils partagés (aucune dépendance, utilisables dans Node pour les tests).

export const $ = (id) => document.getElementById(id);

/** Générateur pseudo-aléatoire reproductible (mulberry32). */
export function rng(graine) {
  let a = graine | 0;
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Nombre au format français : 3,40 */
export const fr = (x, d = 0) => Number(x).toFixed(d).replace('.', ',');
export const euros = (x) => (x == null ? '—' : fr(x, 2) + ' €');

/** Transition douce entre a et b (0 → 1). */
export function sm(a, b, x) {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

/** Petite empreinte d'un texte (pour la démo : même question → même résultat). */
export function empreinte(s) {
  let h = 7;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function el(balise, classe, texte) {
  const d = document.createElement(balise);
  if (classe) d.className = classe;
  if (texte != null) d.textContent = texte;
  return d;
}

export const deuxChiffres = (n) => (n < 10 ? '0' + n : '' + n);
export function heureMinute(d = new Date()) {
  return deuxChiffres(d.getHours()) + ':' + deuxChiffres(d.getMinutes());
}

/** Minuscules sans accents (comme noyau/outils.normaliser). */
export function normaliser(t) {
  return String(t).toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
}

export const mouvementReduit = () =>
  typeof window !== 'undefined' && !!window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** localStorage peut être absent ou bloqué : on n'en dépend jamais. */
export const memoire = {
  lire(cle) { try { return JSON.parse(localStorage.getItem(cle)); } catch (e) { return null; } },
  ecrire(cle, v) { try { localStorage.setItem(cle, JSON.stringify(v)); } catch (e) { /* rien */ } },
};
