// L'intensité de parole de JARVIS : UNE seule source (0 à 1) que toute l'interface lit
// (la sphère, l'onde en bas, l'état affiché). Elle suit le rythme RÉEL de la réponse :
//   - texte qui s'écrit : une impulsion à chaque mot (plus forte pour un mot long),
//     rien sur la ponctuation (une pause) ;
//   - voix du navigateur : une impulsion à chaque mot prononcé (événement « boundary ») ;
//   - fichier audio : une impulsion à chaque pic de volume (Web Audio, AnalyserNode).
// Entre deux impulsions, l'intensité redescend toute seule ; à zéro, plus rien ne tourne.

export function creerParole({ maintenant = () => performance.now(), image = (f) => requestAnimationFrame(f) } = {}) {
  let valeur = 0, parle = false, prevu = false, dernier = 0;
  let origine = null;                            // le projet d'où partent les impulsions
  const abonnes = new Set();
  const prevenir = (e) => abonnes.forEach((f) => { try { f(e); } catch (x) { /* un abonné ne bloque pas les autres */ } });

  function decroitre() {
    prevu = false;
    const t = maintenant(), dt = Math.min(0.1, (t - dernier) / 1000);
    dernier = t;
    valeur = valeur * Math.exp(-dt * 3.2);
    if (valeur < 0.004) valeur = 0;
    prevenir({ type: 'niveau', valeur });
    if (valeur > 0) planifier();
  }
  function planifier() {
    if (prevu) return;
    prevu = true;
    if (!dernier) dernier = maintenant();
    image(decroitre);
  }

  const api = {
    get valeur() { return valeur; },
    get parle() { return parle; },
    get origine() { return origine; },
    /** Début d'une réponse : « origine » = projet concerné (ou null). */
    debut(projet = null) {
      parle = true; origine = projet;
      prevenir({ type: 'debut', origine });
    },
    /** Une impulsion (force de 0 à 1). */
    impulsion(force = 0.6) {
      const f = Math.max(0, Math.min(1, force));
      valeur = Math.max(valeur, f);
      dernier = maintenant();
      prevenir({ type: 'impulsion', force: f, origine });
      planifier();
    },
    /** Fin de la réponse : retour progressif au calme (la décroissance continue seule). */
    fin() {
      parle = false;
      prevenir({ type: 'fin' });
      planifier();
    },
    abonner(f) { abonnes.add(f); return () => abonnes.delete(f); },
    /** Force d'une impulsion pour un mot écrit : rien pour la ponctuation seule. */
    forceMot(mot) {
      const lettres = (mot.match(/[\p{L}\p{N}]/gu) || []).length;
      return lettres ? Math.min(1, 0.35 + lettres / 14) : 0;
    },
    /**
     * Branche un élément audio (voix enregistrée) : une impulsion à chaque pic de volume.
     * Renvoie une fonction pour débrancher.
     */
    brancherAudio(element, Contexte = typeof window !== 'undefined' && (window.AudioContext || window.webkitAudioContext)) {
      if (!Contexte) return () => {};
      const ctx = new Contexte(), src = ctx.createMediaElementSource(element), an = ctx.createAnalyser();
      an.fftSize = 512;
      src.connect(an); an.connect(ctx.destination);
      const tampon = new Float32Array(an.fftSize);
      let moyenne = 0.02, derniere = 0, actif = true;
      (function ecouter() {
        if (!actif) return;
        an.getFloatTimeDomainData(tampon);
        let somme = 0;
        for (let i = 0; i < tampon.length; i++) somme += tampon[i] * tampon[i];
        const rms = Math.sqrt(somme / tampon.length), t = maintenant();
        if (rms > 0.03 && rms > moyenne * 1.35 && t - derniere > 110) { derniere = t; api.impulsion(Math.min(1, rms * 6)); }
        moyenne = moyenne * 0.95 + rms * 0.05;
        if (!element.paused && !element.ended) image(ecouter);
      })();
      const relancer = () => { if (actif) { if (ctx.state === 'suspended') ctx.resume(); image(ecouter); } };
      element.addEventListener('play', relancer);
      return () => { actif = false; element.removeEventListener('play', relancer); try { ctx.close(); } catch (e) { /* rien */ } };
    },
  };
  return api;
}
