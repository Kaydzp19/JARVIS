// Outils de dessin des hologrammes (canvas 2D, devenu texture du panneau 3D).
// Cadre aux coins lumineux, grille fine, jauges, courbes. Couleurs de l'identité JARVIS.

export const COULEURS = { bleu: '#4CC9FF', bleuClair: '#6FD7FF', orange: '#FF8A3D', jaune: '#FFD84A',
  texte: '#F1F8FF', texte2: '#E8F6FF', gris: '#8FA9C2', gris2: '#5E7A94' };
const DISP = "Rajdhani,'Segoe UI',sans-serif", MONO = "'JetBrains Mono',ui-monospace,monospace";
export const fr = (x, d = 0) => Number(x).toFixed(d).replace('.', ',');

export function rr(c, x, y, w, h, r) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}

/** Texte : taille, couleur, graisse, famille ('m' = mono, sinon Rajdhani), alignement. */
export function tx(c, s, x, y, taille, couleur, graisse, famille, aligne) {
  c.font = (graisse || 500) + ' ' + taille + 'px ' + (famille === 'm' ? MONO : DISP);
  c.fillStyle = couleur || COULEURS.texte2; c.textAlign = aligne || 'left'; c.textBaseline = 'alphabetic';
  c.fillText(s, x, y);
}

/** Coupe un texte trop long avec « … ». */
export function couper(c, s, largeur) {
  s = String(s);
  if (c.measureText(s).width <= largeur) return s;
  while (s.length > 1 && c.measureText(s + '…').width > largeur) s = s.slice(0, -1);
  return s + '…';
}

/** Le cadre : fond, grille, coins lumineux, titre espacé et sous-titre. Renvoie la zone utile. */
export function cadre(c, W, H, titre, sous, basMin = 0) {
  c.clearRect(0, 0, W, H); c.shadowBlur = 0;
  c.fillStyle = 'rgba(3,10,24,0.80)'; rr(c, 2, 2, W - 4, H - 4, 10); c.fill();
  c.strokeStyle = 'rgba(110,200,255,0.28)'; c.lineWidth = 1; rr(c, 2.5, 2.5, W - 5, H - 5, 10); c.stroke();
  c.strokeStyle = 'rgba(110,200,255,0.05)';
  for (let x = 20; x < W; x += 26) { c.beginPath(); c.moveTo(x, 6); c.lineTo(x, H - 6); c.stroke(); }
  for (let y = 20; y < H; y += 26) { c.beginPath(); c.moveTo(6, y); c.lineTo(W - 6, y); c.stroke(); }
  c.strokeStyle = COULEURS.bleuClair; c.lineWidth = 2; c.shadowColor = COULEURS.bleu; c.shadowBlur = 10;
  const L = 16;
  [[2, 2, 1, 1], [W - 2, 2, -1, 1], [2, H - 2, 1, -1], [W - 2, H - 2, -1, -1]].forEach((q) => {
    c.beginPath(); c.moveTo(q[0] + q[2] * L, q[1]); c.lineTo(q[0], q[1]); c.lineTo(q[0], q[1] + q[3] * L); c.stroke();
  });
  c.shadowBlur = 0;
  c.fillStyle = COULEURS.bleu; c.fillRect(18, 22, 12, 2);
  const T = String(titre).toUpperCase();
  let tt = T.split('').join(' '), fs = 19;
  c.font = '700 19px ' + DISP;
  if (c.measureText(tt).width > W * 0.5) tt = T;
  const place = W - 38 - 96;              // à droite : boutons épingler et fermer
  while (c.measureText(tt).width > place * (sous ? 0.62 : 1) && fs > 12) { fs--; c.font = '700 ' + fs + 'px ' + DISP; }
  tt = couper(c, tt, place * (sous ? 0.62 : 1));
  tx(c, tt, 38, 28, fs, COULEURS.texte, 700);
  const largeurTitre = c.measureText(tt).width;       // mesurée avec la police du titre
  if (sous) {
    let sf = W < 420 ? 9.5 : 11;
    c.font = '400 ' + sf + 'px ' + MONO;
    const reste = place - largeurTitre - 20;
    while (c.measureText(sous).width > reste && sf > 7.5) { sf -= 0.5; c.font = '400 ' + sf + 'px ' + MONO; }
    if (reste > 60) tx(c, couper(c, sous, reste), 38 + place, 27, sf, COULEURS.gris, 400, 'm', 'right');
  }
  const bas = Math.max(basMin, W < 560 ? 84 : 46);                      // en bas : contrôles et actions (sur 2 lignes si étroit)
  return { x: 18, y: 46, w: W - 36, h: H - 46 - bas };
}

export function jauge(c, cx, cy, r, v, texte, etiquette, couleur) {
  couleur = couleur || COULEURS.bleu;
  c.lineWidth = Math.max(4, r * 0.18); c.lineCap = 'round';
  c.strokeStyle = 'rgba(120,200,255,0.16)'; c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.stroke();
  if (v != null) {
    c.strokeStyle = couleur; c.shadowColor = couleur; c.shadowBlur = 9;
    c.beginPath(); c.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0.02, Math.min(1, v))); c.stroke();
    c.shadowBlur = 0;
  }
  c.lineCap = 'butt';
  tx(c, texte, cx, cy + r * 0.2, r * (String(texte).length > 4 ? 0.42 : 0.6), '#fff', 700, 'd', 'center');
  tx(c, etiquette, cx, cy + r + 15, Math.max(9, r * 0.3), COULEURS.gris, 500, 'm', 'center');
}

/** Courbe (0 – max) avec aire dégradée. Renvoie la position de chaque point (pour les infobulles). */
export function courbe(c, x, y, w, h, valeurs, max = 100, couleur = COULEURS.bleu) {
  c.strokeStyle = 'rgba(120,200,255,0.12)'; c.lineWidth = 1;
  for (let g = 1; g < 4; g++) { c.beginPath(); c.moveTo(x, y + h * g / 4); c.lineTo(x + w, y + h * g / 4); c.stroke(); }
  const pts = valeurs.map((v, i) => ({ x: x + w * i / Math.max(1, valeurs.length - 1), y: y + h - (Math.min(max, Math.max(0, v || 0)) / max) * h, v }));
  if (pts.length < 2) return pts;
  const gr = c.createLinearGradient(0, y, 0, y + h);
  gr.addColorStop(0, 'rgba(76,201,255,0.35)'); gr.addColorStop(1, 'rgba(76,201,255,0)');
  c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(p.x, p.y) : c.moveTo(p.x, p.y)));
  c.strokeStyle = couleur; c.lineWidth = 2; c.shadowColor = couleur; c.shadowBlur = 7; c.stroke(); c.shadowBlur = 0;
  c.lineTo(x + w, y + h); c.lineTo(x, y + h); c.closePath(); c.fillStyle = gr; c.fill();
  return pts;
}

/** Ligne avec barre de proportion (processus, notes). */
export function ligne(c, x, y, w, etiquette, valeur, v, hauteur, couleur = COULEURS.bleu, couleurTexte = COULEURS.texte2) {
  c.font = '500 ' + Math.min(15, hauteur * 0.72) + 'px ' + DISP;
  const lab = couper(c, etiquette, w * 0.72);
  tx(c, lab, x, y, Math.min(15, hauteur * 0.72), couleurTexte, 500);
  tx(c, valeur, x + w, y, Math.min(11, hauteur * 0.55), COULEURS.gris, 400, 'm', 'right');
  c.fillStyle = 'rgba(120,200,255,0.14)'; c.fillRect(x, y + 4, w, 3);
  c.fillStyle = couleur; c.shadowColor = couleur; c.shadowBlur = 6;
  c.fillRect(x, y + 4, w * Math.max(0.02, Math.min(1, v || 0)), 3); c.shadowBlur = 0;
}

export const section = (c, s, x, y) => tx(c, s, x, y, 9.5, COULEURS.gris, 500, 'm');
