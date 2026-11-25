// Colonne de gauche : la conversation avec JARVIS.
// Messages, ligne d'outil brute (ex. se_souvenir(projet="A", requête="…") et « routeur :
// aucun appel IA »), suggestions rapides, champ de saisie, micro (plus tard), envoi.
// État affiché en haut : VEILLE, ÉCOUTE, ANALYSE, RÉPONSE.

import { $, el, mouvementReduit } from './outils.js';

const LIBELLES = { VEILLE: 'VEILLE', ECOUTE: 'ÉCOUTE', ANALYSE: 'ANALYSE', REPONSE: 'RÉPONSE' };

export function creerConversation({ sphere, parole, surQuestion }) {
  const messages = $('messages'), champ = $('question'), suggestions = $('suggestions');
  const reduit = mouvementReduit();
  let occupe = false, voixActive = false;
  const tts = !!(window.speechSynthesis && window.SpeechSynthesisUtterance);

  function etat(s) {
    $('etat').dataset.s = s;
    $('etat-texte').textContent = LIBELLES[s];
  }
  function ajouter(genre, qui, texte) {
    const m = el('div', 'm ' + genre);
    m.appendChild(el('div', 'qui', qui));
    const t = el('div', 'tx');
    t.textContent = texte || '';
    m.appendChild(t);
    messages.appendChild(m);
    messages.scrollTop = messages.scrollHeight;
    return t;
  }
  /** Ligne d'outil : le texte brut de l'appel, puis une ou plusieurs remarques en gris. */
  function outil(appel, ...remarques) {
    const t = ajouter('t', 'OUTIL', appel);
    remarques.filter(Boolean).forEach((r) => {
      t.appendChild(el('br'));
      t.appendChild(el('em', r.prive ? 'verrou' : '', r.texte || r));
    });
    return { completer(texte) { t.appendChild(el('br')); t.appendChild(document.createTextNode(texte)); } };
  }
  /**
   * JARVIS parle : le texte s'écrit (ou la voix le lit). Chaque mot envoie une impulsion
   * à la source unique d'intensité de parole ; « origine » = projet concerné.
   */
  function dire(texte, { origine = null } = {}) {
    return new Promise((resolve) => {
      const t = ajouter('j', 'JARVIS', '');
      etat('REPONSE');
      parole.debut(origine);
      let i = 0, attendre = 1, fini = false, voix = false;
      const fin = () => {
        if (fini || --attendre > 0) return;
        fini = true;
        setTimeout(() => {
          parole.fin();
          etat(document.activeElement === champ ? 'ECOUTE' : 'VEILLE');
          resolve();
        }, 450);
      };
      if (voixActive && tts) {
        try {
          attendre = 2; voix = true;
          speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(texte);
          u.lang = 'fr-FR'; u.onend = fin; u.onerror = fin;
          // une impulsion par mot prononcé (rythme réel de la voix)
          u.onboundary = (e) => {
            if (e.name && e.name !== 'word') return;
            const mot = texte.slice(e.charIndex, e.charIndex + (e.charLength || 8)).split(/\s/)[0];
            parole.impulsion(parole.forceMot(mot) || 0.4);
          };
          speechSynthesis.speak(u);
          setTimeout(() => { attendre = 1; fin(); }, Math.max(9000, texte.length * 110));
        } catch (e) { attendre = 1; voix = false; }
      }
      const mots = texte.split(/(\s+)/);      // mots et espaces, dans l'ordre
      let m = 0;
      (function pas() {
        if (reduit) { t.textContent = texte; if (!voix) parole.impulsion(0.6); fin(); return; }
        const morceau = mots[m++] || '';
        i += morceau.length;
        t.textContent = texte.slice(0, i);
        messages.scrollTop = messages.scrollHeight;
        if (!voix && morceau.trim()) parole.impulsion(parole.forceMot(morceau));
        if (m < mots.length) setTimeout(pas, morceau.trim() ? 40 + morceau.length * 14 : 10);
        else fin();
      })();
    });
  }
  function verrouiller(on) {
    occupe = on;
    Array.from(suggestions.children).forEach((b) => { b.disabled = on; });
    champ.disabled = on;
    if (!on) champ.focus({ preventScroll: true });
  }
  function proposer(liste) {
    suggestions.textContent = '';
    liste.forEach((c) => {
      const b = el('button', '', c);
      b.type = 'button';
      b.addEventListener('click', () => !occupe && surQuestion(c));
      suggestions.appendChild(b);
    });
  }

  $('formulaire').addEventListener('submit', (e) => {
    e.preventDefault();
    const v = champ.value.trim();
    if (!v || occupe) return;
    champ.value = '';
    surQuestion(v);
  });
  champ.addEventListener('focus', () => { sphere && sphere.ecouter(true); if (!occupe) etat('ECOUTE'); });
  champ.addEventListener('blur', () => { sphere && sphere.ecouter(false); if (!occupe) etat('VEILLE'); });
  const bv = $('voix');
  if (!tts) { bv.textContent = 'VOIX · INDISPO.'; bv.disabled = true; }
  bv.addEventListener('click', () => {
    voixActive = !voixActive && tts;
    bv.setAttribute('aria-pressed', voixActive ? 'true' : 'false');
    bv.textContent = 'VOIX · ' + (voixActive ? 'OUI' : 'NON');
    if (!voixActive && tts) { try { speechSynthesis.cancel(); } catch (e) { /* rien */ } }
  });

  return { etat, ajouter, outil, dire, verrouiller, proposer, get occupe() { return occupe; } };
}
