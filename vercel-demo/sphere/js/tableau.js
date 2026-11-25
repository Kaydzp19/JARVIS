// Colonne de droite : les widgets permanents.
//   Système        CPU, RAM, disque, batterie (lecture seule, jamais de sudo)
//   Dépense IA     session, aujourd'hui, ce mois, plafond
//   À valider      propositions en attente : Valider / Refuser (seul Kayd décide)
//   Journal du jour  contenu des projets sensibles masqué

import { $, el, euros, fr } from './outils.js';

export function creerTableau({ source, surDecision, surPlanif, surRappel }) {
  const barres = {};
  ['CPU', 'RAM', 'DISQUE', 'BATT.'].forEach((nom) => {
    const r = el('div', 'barre');
    r.appendChild(el('span', '', nom));
    const p = el('div', 'pis'); p.appendChild(el('b')); r.appendChild(p);
    r.appendChild(el('span', '', '—'));
    $('sys-barres').appendChild(r);
    barres[nom] = r;
  });
  const barre = (nom, pourcent, texte) => {
    const r = barres[nom];
    r.querySelector('.pis b').style.width = (pourcent == null ? 0 : Math.max(0, Math.min(100, pourcent))) + '%';
    r.lastChild.textContent = texte;
  };
  let derniereMachine = null;

  async function systeme() {
    try {
      const m = await source.systeme();
      derniereMachine = m;
      $('sys-nom').textContent = m.systeme === 'Darwin' ? 'Mac' : (m.systeme || 'machine');
      barre('CPU', m.cpu, m.cpu == null ? 'indisponible' : fr(m.cpu, 0) + ' %');
      barre('RAM', m.ram && m.ram.pourcent, m.ram ? `${fr(m.ram.utilisee_go, 1)} / ${fr(m.ram.totale_go, 0)} Go` : 'indisponible');
      barre('DISQUE', m.disque && m.disque.pourcent, m.disque ? `${fr(m.disque.utilise_go, 0)} / ${fr(m.disque.total_go, 0)} Go` : 'indisponible');
      barre('BATT.', m.batterie && m.batterie.pourcent, m.batterie ? `${m.batterie.pourcent} %${m.batterie.en_charge ? ' · secteur' : ''}` : 'sans batterie');
    } catch (e) { /* le widget garde ses valeurs */ }
    return derniereMachine;
  }

  async function depenses() {
    try {
      const d = await source.depenses();
      $('dep-session').textContent = euros(d.session);
      $('dep-jour').textContent = euros(d.aujourd_hui);
      $('dep-mois').textContent = euros(d.mois);
      $('dep-plafond').textContent = 'plafond ' + fr(d.plafond, 0) + ' €';
      const part = d.plafond ? Math.min(100, 100 * d.mois / d.plafond) : 0;
      $('dep-barre').querySelector('b').style.width = part + '%';
      $('dep-barre').classList.toggle('haut', part >= 80);
      $('dep-texte').textContent = d.mode_ia === 'simule'
        ? 'IA simulée : aucun appel payant. Local d’abord, cloud seulement pour les grosses tâches.'
        : 'Local d’abord, cloud seulement pour les grosses tâches.';
    } catch (e) { /* rien */ }
  }

  let attente = [];
  async function aValider() {
    try { attente = await source.aValider(); } catch (e) { attente = []; }
    const u = $('a-valider');
    u.textContent = '';
    $('nb-a-valider').textContent = attente.length;
    if (!attente.length) { u.appendChild(el('li', 'vide', 'Rien à valider pour l’instant.')); return attente; }
    attente.forEach((p) => {
      const li = el('li');
      li.appendChild(el('div', 't', p.titre));
      li.appendChild(el('div', 's', `${p.projet} · ${p.raison || p.acteur || p.type}`));
      const b = el('div', 'bt');
      const ok = el('button', 'ok', 'Valider'), non = el('button', '', 'Refuser');
      ok.type = non.type = 'button';
      ok.setAttribute('aria-label', 'Valider : ' + p.titre);
      non.setAttribute('aria-label', 'Refuser : ' + p.titre);
      ok.addEventListener('click', () => surDecision(p, true));
      non.addEventListener('click', () => surDecision(p, false));
      b.appendChild(ok); b.appendChild(non);
      li.appendChild(b);
      u.appendChild(li);
    });
    return attente;
  }

  async function journal() {
    let lignes = [];
    try { lignes = await source.journalDuJour(); } catch (e) { /* rien */ }
    const u = $('journal');
    u.textContent = '';
    if (!lignes.length) { u.appendChild(el('li', 'vide', 'Rien pour l’instant aujourd’hui.')); return; }
    lignes.slice(0, 6).forEach((l) => {
      const li = el('li');
      li.appendChild(el('b', '', l.heure || (l.date || '').slice(11, 16)));
      const d = el('div');
      d.appendChild(document.createTextNode(`${l.acteur} · `));
      d.appendChild(el('span', l.prive ? 'prive' : '', l.evenement));
      li.appendChild(d);
      u.appendChild(li);
    });
  }

  // ---- Planification : les 3 prochaines tâches (vue transversale, lecture seule) ----
  const libelleQuand = (t) => {
    const auj = new Date(), deux = (n) => String(n).padStart(2, '0');
    const iso = (d) => `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`;
    const demain = new Date(auj); demain.setDate(auj.getDate() + 1);
    const jour = t.date === iso(auj) ? 'aujourd’hui' : t.date === iso(demain) ? 'demain'
      : new Date(t.date + 'T12:00').toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' }).replace('.', '');
    return jour + (t.heure ? ' · ' + t.heure : '');
  };
  async function planif() {
    let liste = [];
    try { liste = await source.prochaines(3); } catch (e) { /* rien */ }
    const u = $('planif-liste');
    u.textContent = '';
    if (!liste.length) { u.appendChild(el('li', 'vide', 'Aucune tâche à venir.')); return liste; }
    liste.forEach((t) => {
      const li = el('li'), b = el('button');
      b.type = 'button';
      b.appendChild(el('span', 't', t.titre));
      b.appendChild(el('span', 'q', libelleQuand(t)));
      b.appendChild(el('span', 'p', t.projet + (t.recurrence !== 'aucune' ? ' · récurrente' : '')));
      b.setAttribute('aria-label', `${t.titre}, ${libelleQuand(t)}, ${t.projet} : ouvrir la planification`);
      b.addEventListener('click', () => surPlanif && surPlanif(t));
      li.appendChild(b); u.appendChild(li);
    });
    return liste;
  }
  // Rappels : une seule fois par tâche et par date, quand l'heure du rappel arrive.
  const rappeles = new Set();
  async function rappels() {
    if (!surRappel) return;
    let liste = [];
    try { liste = await source.prochaines(10); } catch (e) { return; }
    const maintenant = Date.now();
    liste.forEach((t) => {
      if (t.rappel == null || !t.date || !t.heure) return;
      const debut = new Date(`${t.date}T${t.heure}:00`).getTime(), cle = `${t.projet}:${t.id}:${t.date}`;
      if (!rappeles.has(cle) && maintenant >= debut - t.rappel * 60000 && maintenant < debut) { rappeles.add(cle); surRappel(t); }
    });
  }

  function demarrer() {
    systeme(); depenses(); aValider(); journal(); planif(); rappels();
    // Pas de mise à jour quand l'onglet est caché (aucun travail inutile).
    const siVisible = (f) => () => { if (!document.hidden) f(); };
    setInterval(siVisible(systeme), 5000);
    setInterval(siVisible(depenses), 30000);
    setInterval(siVisible(journal), 15000);
    setInterval(siVisible(planif), 60000);
    setInterval(rappels, 30000);
  }

  return { demarrer, systeme, depenses, aValider, journal, planif, get machine() { return derniereMachine; }, get attente() { return attente; } };
}
