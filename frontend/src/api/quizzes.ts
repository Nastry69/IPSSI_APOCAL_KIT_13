import { api } from './client';

export type Question = {
  index: number;
  prompt: string;
  options: string[];
  correct_index: number;
};

export type Quiz = {
  id: number;
  title: string;
  source_text: string;
  score: number | null;
  created_at: string;
  questions: Question[];
};

export type QuizSummary = {
  id: number;
  title: string;
  score: number | null;
  nb_questions: number;
  created_at: string;
};

type PaginatedQuizzes = {
  count: number;
  next: string | null;
  previous: string | null;
  results: QuizSummary[];
};

export type AnswerDetail = {
  index: number;
  selected_index: number;
  correct_index: number;
  correct: boolean;
};

export type AnswerResult = {
  score: number;
  total: number;
  details: AnswerDetail[];
  /** Identifiant de la tentative enregistrée (Release 2). */
  attempt_id: number;
  /** Numéro de la tentative pour ce quiz (1, 2, 3…). */
  number: number;
};

export async function listQuizzes(): Promise<PaginatedQuizzes> {
  const { data } = await api.get<PaginatedQuizzes>('/quizzes/');
  return data;
}

export async function getQuiz(id: number): Promise<Quiz> {
  const { data } = await api.get<Quiz>(`/quizzes/${id}/`);
  return data;
}

export async function submitAnswers(
  quizId: number,
  answers: { index: number; selected_index: number }[],
  /**
   * Ordre d'affichage des questions (liste d'index). Optionnel : utilisé par le
   * mode « Refaire mélangé » (Release 2) pour tracer l'ordre présenté au candidat.
   */
  questionOrder?: number[],
): Promise<AnswerResult> {
  const body: {
    answers: { index: number; selected_index: number }[];
    question_order?: number[];
  } = { answers };
  if (questionOrder) body.question_order = questionOrder;
  const { data } = await api.post<AnswerResult>(`/quizzes/${quizId}/answer/`, body);
  return data;
}

// ---------------------------------------------------------------------------
// MVP2 (Lot 6) — Dashboard de progression & Révision des erreurs
// ---------------------------------------------------------------------------

export type ScorePoint = {
  id: number;
  title: string;
  score: number;
  created_at: string;
};

export type Stats = {
  total_quizzes: number;
  quizzes_taken: number;
  average_score: number | null;
  best_score: number | null;
  last_score: number | null;
  questions_answered: number;
  questions_correct: number;
  accuracy: number | null;
  history: ScorePoint[];
};

export type Mistake = {
  quiz_id: number;
  quiz_title: string;
  index: number;
  prompt: string;
  options: string[];
  correct_index: number;
  selected_index: number;
};

/** Statistiques de progression de l'utilisateur connecté. */
export async function getStats(): Promise<Stats> {
  const { data } = await api.get<Stats>('/quizzes/stats/');
  return data;
}

/** Liste des questions ratées (pour la révision des erreurs). */
export async function getMistakes(): Promise<{ count: number; mistakes: Mistake[] }> {
  const { data } = await api.get<{ count: number; mistakes: Mistake[] }>('/quizzes/mistakes/');
  return data;
}

// ---------------------------------------------------------------------------
// Release 2 — Historique des tentatives & retest mélangé
// ---------------------------------------------------------------------------

/** Résumé d'une tentative (une ligne de l'historique d'un quiz). */
export type Attempt = {
  id: number;
  /** Numéro de la tentative pour ce quiz (1, 2, 3…). */
  number: number;
  score: number;
  total: number;
  created_at: string;
};

/** Une réponse rejouée dans le détail d'une tentative. */
export type AttemptAnswer = {
  index: number;
  prompt: string;
  options: string[];
  correct_index: number;
  selected_index: number;
  is_correct: boolean;
};

/** Détail complet d'une tentative (pour la rejouer avec corrections). */
export type AttemptDetail = {
  id: number;
  number: number;
  score: number;
  total: number;
  created_at: string;
  answers: AttemptAnswer[];
};

/** Liste des tentatives d'un quiz (les plus récentes d'abord). */
export async function getAttempts(quizId: number): Promise<Attempt[]> {
  const { data } = await api.get<Attempt[]>(`/quizzes/${quizId}/attempts/`);
  return data;
}

/** Détail d'une tentative précise, avec les réponses corrigées. */
export async function getAttemptDetail(quizId: number, attemptId: number): Promise<AttemptDetail> {
  const { data } = await api.get<AttemptDetail>(`/quizzes/${quizId}/attempts/${attemptId}/`);
  return data;
}
