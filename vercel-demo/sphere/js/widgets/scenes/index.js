// Les scènes connues de l'interface ; toute autre scène utilise le widget générique.
import generique from './generique.js';
import graphique from './graphique.js';
import machine from './machine.js';
import meteo from './meteo.js';
import note_privee from './note_privee.js';
import notes_retenues from './notes_retenues.js';
import planification from './planification.js';
import resume_nuit from './resume_nuit.js';

export const SCENES = { notes_retenues, graphique, machine, meteo, resume_nuit, note_privee, planification };
export const sceneDe = (nom) => SCENES[nom] || generique;
