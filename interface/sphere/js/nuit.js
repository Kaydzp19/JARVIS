// La nuit, en 4 phases accélérées (environ 9 secondes), à partir d'un bilan DÉJÀ calculé :
//   TRI      oubli de 2 %, apprentissage +0,10 : les synapses renforcées scintillent,
//            celles qui passent sous 0,05 s'éteignent (archivage) ;
//   ANALYSE  chaque projet est relu, séparément (un balayage par région) ;
//   RÊVE     5 arcs orange pointillés par projet rapprochent des notes éloignées ;
//   RÉVEIL   la meilleure idée devient une proposition JAUNE (deux anneaux sur ses notes,
//            carte « À valider ») ; les autres arcs s'effacent.
// Rien n'est écrit sans validation : l'animation ne fait que montrer le bilan.

export const TEMPS_NUIT = [0, 2.2, 4.0, 6.8, 9.0];
export const TEXTES_NUIT = ['TRI · oubli de 2 %, apprentissage +0,10', 'ANALYSE · chaque projet relu séparément',
  'RÊVE · notes éloignées rapprochées', 'RÉVEIL · la meilleure idée est gardée'];

export function installerNuit(S, f) {
  const phase = (t) => { if (S.ecrirePhase) S.ecrirePhase(t); };

  function arete(projet, a, b) {
    const pj = S.projets.findIndex((p) => p.nom === projet);
    const ia = S.index.get(pj + ':' + a), ib = S.index.get(pj + ':' + b);
    if (ia == null || ib == null) return -1;
    const k = S.noeuds[ia].aretes.find((x) => { const e = S.aretes[x]; return !e.reve && ((e.a === ia && e.b === ib) || (e.a === ib && e.b === ia)); });
    return k == null ? -1 : k;
  }

  function lancer(bilan) {
    if (S.vague || S.nuitS) return Promise.resolve(null);
    return new Promise((resolve) => {
      S.nuitS = {
        t: 0, ph: -1, resolve, bilan,
        renforcees: bilan.renforcees.map((x) => arete(x.projet, x.a, x.b)).filter((k) => k >= 0),
        mourantes: bilan.archivees.map((x) => arete(x.projet, x.a, x.b)).filter((k) => k >= 0),
        reves: S.aretes.map((e, k) => k).filter((k) => S.aretes[k].reve && S.aretes[k].mode !== 1),
      };
    });
  }

  function entrer(ph) {
    const n = S.nuitS;
    n.ph = ph;
    if (ph < 4) phase(`NUIT · ${ph + 1} · ${TEXTES_NUIT[ph]}`);
    if (ph === 1) {
      n.mourantes.forEach((k) => { S.aretes[k].vivante = 0; });
      S.arch += n.mourantes.length;
      f.rafraichirEtat(); f.compter();
    } else if (ph === 2) {
      n.reves.forEach((k) => { const e = S.aretes[k]; e.vivante = 0; e.mode = 2; });
    } else if (ph === 3) {
      n.bilan.propositions.forEach((p) => f.ajouterAlerte(p));
      n.reves = n.reves.filter((k) => S.aretes[k].mode === 2);
    } else if (ph === 4) {
      n.reves.forEach((k) => { const e = S.aretes[k]; if (e.mode === 2) e.vivante = 0; });
      f.rafraichirEtat();
      for (let i = 0; i < S.N; i++) S.act[i] = 0;
      f.pousserActivite();
      const info = { renforcees: n.bilan.renforcees.length, archivees: n.bilan.archivees.length,
        idees: n.bilan.propositions.length };
      phase(`NUIT TERMINÉE · ${info.renforcees} renforcées · ${info.archivees} archivées · ${info.idees} en attente`);
      setTimeout(() => { if (!S.nuitS && !S.vague) phase(''); }, 4000);
      S.nuitS = null;
      n.resolve(info);
    }
  }

  function etape(dt, maintenant) {
    const n = S.nuitS;
    if (!n) return;
    n.t += dt;
    const T = TEMPS_NUIT;
    const ph = n.t < T[1] ? 0 : n.t < T[2] ? 1 : n.t < T[3] ? 2 : n.t < T[4] ? 3 : 4;
    while (S.nuitS && n.ph < ph) entrer(n.ph + 1);
    if (!S.nuitS) return;
    const prog = Math.min(1, (n.t - T[ph]) / (T[ph + 1] - T[ph])), B = S.A.b;
    const ecrire = (e, z, mode) => { for (let k = e.debut; k < e.debut + e.nb; k++) { B[k * 4 + 2] = z; if (mode != null) B[k * 4 + 3] = mode; } };
    if (ph === 0) {
      S.aretes.forEach((e) => { if (!e.reve) ecrire(e, e.vivante); });
      n.renforcees.forEach((k) => ecrire(S.aretes[k], 0.55 + 0.45 * Math.sin(maintenant / 70 + k)));
      n.mourantes.forEach((k) => ecrire(S.aretes[k], Math.max(0, 1 - prog) * (0.5 + 0.5 * Math.sin(maintenant / 45))));
      S.geo.attributes.aB.needsUpdate = true;
    } else if (ph === 1) {
      for (let i = 0; i < S.N; i++) {
        const y = (S.noeuds[i].p.y + 1) / 2, d = Math.abs(y - ((prog * 2) % 1));
        S.act[i] = 0.55 * Math.exp(-d * d * 260);
      }
      S.actSale = true;
    } else if (ph === 2) {
      for (let i = 0; i < S.N; i++) S.act[i] = 0;
      S.actSale = true;
      const parProjet = {};
      n.reves.forEach((k) => {
        const e = S.aretes[k], ix = (parProjet[e.proj] = (parProjet[e.proj] || 0) + 1) - 1;
        e.vivante = 0.85 * Math.max(0, Math.min(1, prog * 1.6 - ix / 5 * 0.6));
        ecrire(e, e.vivante, 2);
      });
      S.geo.attributes.aB.needsUpdate = true;
    } else if (ph === 3) {
      n.reves.forEach((k) => { const e = S.aretes[k]; if (e.mode === 2) { e.vivante = 0.85 * (1 - prog); ecrire(e, e.vivante, 2); } });
      S.geo.attributes.aB.needsUpdate = true;
    }
  }

  return { lancer, etape };
}
