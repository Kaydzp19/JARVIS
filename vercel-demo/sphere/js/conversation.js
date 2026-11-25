// Colonne de gauche : la conversation avec JARVIS.
// Messages, ligne d'outil brute (ex. se_souvenir(projet="A", requête="…") et « routeur :
// aucun appel IA »), suggestions rapides, champ de saisie, micro (plus tard), envoi.
// État affiché en haut : VEILLE, ÉCOUTE, ANALYSE, RÉPONSE.

import { $, el, mouvementReduit } from './outils.js';

const LIBELLES = { VEILLE: 'VEILLE', ECOUTE: 'ÉCOUTE', ANALYSE: 'ANALYSE', REPONSE: 'RÉPONSE' };

export function creerConversation({ sphere, surQuestion }) {
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
  /** JARVIS parle : le texte s'écrit, la sphère pulse (pauses sur les espaces), voix si activée. */
  function dire(texte) {
    return new Promise((resolve) => {
      const t = ajouter('j', 'JARVIS', '');
      etat('REPONSE');
      let i = 0, attendre = 1, fini = false;
      const fin = () => {
        if (fini || --attendre > 0) return;
        fini = true;
        setTimeout(() => {
          sphere && sphere.parler(0);
          etat(document.activeElement === champ ? 'ECOUTE' : 'VEILLE');
          resolve();
        }, 450);
      };
      if (voixActive && tts) {
        try {
          attendre = 2;
          speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(texte);
          u.lang = 'fr-FR'; u.onend = fin; u.onerror = fin;
          u.onboundary = () => sphere && sphere.parler(1);
          speechSynthesis.speak(u);
          setTimeout(() => { attendre = 1; fin(); }, Math.max(9000, texte.length * 110));
        } catch (e) { attendre = 1; }
      }
      (function pas() {
        i += reduit ? texte.length : 2;
        t.textContent = texte.slice(0, i);
        messages.scrollTop = messages.scrollHeight;
        const c = texte.charAt(Math.min(i, texte.length) - 1);
        if (sphere) sphere.parler(/[\s,.;:!?’'()]/.test(c) ? 0.1 : 0.45 + 0.55 * Math.abs(Math.sin(i * 0.9)));
        if (i < texte.length) setTimeout(pas, 18); else fin();
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
