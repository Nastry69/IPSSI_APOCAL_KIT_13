import { api } from './client';
import type { Quiz } from './quizzes';

export type LLMPing = {
  backend: 'ollama' | 'mock';
  model: string;
  ollama_alive: boolean;
  model_loaded?: boolean;
  message: string;
};

/** Niveaux de difficulté acceptés par le backend (`generate-quiz`). Défaut : "medium". */
export type QuizDifficulty = 'easy' | 'medium' | 'hard';

/**
 * Document d'étude généré par le LLM (fiche de révision ou résumé).
 * `content` est du texte/markdown affiché tel quel (Release 2 — Feature #1).
 */
export type StudyDoc = {
  id: number;
  kind: 'note' | 'summary';
  title: string;
  content: string;
  created_at: string;
};

export async function ping(): Promise<LLMPing> {
  const { data } = await api.get<LLMPing>('/llm/ping/');
  return data;
}

/**
 * Génère un quiz à partir d'un PDF ou d'un texte.
 * Renvoie le quiz complet (avec les 10 questions et leur bonne réponse).
 */
export async function generateQuiz(input: {
  title: string;
  pdf?: File;
  source_text?: string;
  /** Niveau de difficulté des questions générées (défaut backend : "medium"). */
  difficulty?: QuizDifficulty;
  /** Nombre de questions à générer, entre 5 et 20 (défaut backend : 10). */
  num_questions?: number;
  /** Thème/chapitre ciblé, optionnel (texte libre). */
  theme?: string;
}): Promise<Quiz> {
  const form = new FormData();
  form.append('title', input.title);
  if (input.pdf) form.append('pdf', input.pdf);
  if (input.source_text) form.append('source_text', input.source_text);
  if (input.difficulty) form.append('difficulty', input.difficulty);
  if (input.num_questions !== undefined) form.append('num_questions', String(input.num_questions));
  if (input.theme) form.append('theme', input.theme);

  const { data } = await api.post<Quiz>('/llm/generate-quiz/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // La génération LLM sur CPU peut prendre plusieurs minutes : on dépasse
    // largement le timeout axios par défaut (120 s). Aligné sur OLLAMA_TIMEOUT.
    timeout: 600_000,
  });
  return data;
}

// ---------------------------------------------------------------------------
// Release 2 — Feature #1 : documents d'étude (fiche de révision & résumé)
// ---------------------------------------------------------------------------

/** Entrée commune aux générateurs de documents d'étude (fiche / résumé). */
type StudyDocInput = {
  title: string;
  pdf?: File;
  source_text?: string;
};

/**
 * Construit le FormData d'une génération de document d'étude.
 * Même logique que `generateQuiz` : PDF ou texte source selon le mode choisi.
 */
function buildStudyDocForm(input: StudyDocInput): FormData {
  const form = new FormData();
  form.append('title', input.title);
  if (input.pdf) form.append('pdf', input.pdf);
  if (input.source_text) form.append('source_text', input.source_text);
  return form;
}

/** Génère une fiche de révision à partir d'un PDF ou d'un texte. */
export async function generateNote(input: StudyDocInput): Promise<StudyDoc> {
  const { data } = await api.post<StudyDoc>('/llm/generate-note/', buildStudyDocForm(input), {
    headers: { 'Content-Type': 'multipart/form-data' },
    // Même contrainte de durée que la génération de quiz (LLM sur CPU).
    timeout: 600_000,
  });
  return data;
}

/** Génère un résumé à partir d'un PDF ou d'un texte. */
export async function generateSummary(input: StudyDocInput): Promise<StudyDoc> {
  const { data } = await api.post<StudyDoc>('/llm/generate-summary/', buildStudyDocForm(input), {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600_000,
  });
  return data;
}

/** Récupère un document d'étude (fiche ou résumé) par son identifiant. */
export async function getStudyDoc(id: number): Promise<StudyDoc> {
  const { data } = await api.get<StudyDoc>(`/llm/study-docs/${id}/`);
  return data;
}
