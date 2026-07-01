/**
 * Appels API liés aux classes (Release 2 — Espace prof).
 *
 * Une « classe » (Classroom) relie un enseignant à ses élèves via un code
 * d'invitation. L'enseignant peut ensuite suivre la progression de ses élèves
 * (KPIs + évolution des scores) et consulter le détail des tentatives.
 *
 * Contrat backend :
 *   GET /api/classes/                                                → Classroom[]
 *   GET /api/classes/<id>/progress/                                  → StudentProgress[]
 *   GET /api/classes/<id>/students/<studentId>/attempts/<attemptId>/ → StudentAttemptDetail
 */
import { api } from './client';

/** Une classe telle que renvoyée par ClassroomSerializer (côté enseignant). */
export type Classroom = {
  id: number;
  /** Nom de la classe (champ `name` du serializer ; `title` toléré en repli). */
  name?: string;
  title?: string;
  code: string;
  student_count: number;
  teacher_name?: string;
  created_at?: string;
};

/** Résumé d'un élève affiché dans la liste des classes (pour le libellé). */
export type ClassStudent = {
  id: number;
  first_name: string;
  last_name: string;
  username: string;
};

/** Un point d'évolution : une tentative passée par l'élève. */
export type EvolutionPoint = {
  attempt_id: number;
  quiz_id: number;
  quiz_title: string;
  number: number;
  score: number;
  total: number;
  created_at: string;
};

/** Progression d'un élève dans une classe (KPIs + courbe d'évolution). */
export type StudentProgress = {
  student: ClassStudent;
  quizzes_taken: number;
  average_score: number | null;
  best_score: number | null;
  last_score: number | null;
  evolution: EvolutionPoint[];
};

/** Une réponse d'une tentative, vue par l'enseignant (avec correction). */
export type StudentAttemptAnswer = {
  index: number;
  prompt: string;
  options: string[];
  correct_index: number;
  selected_index: number;
  is_correct: boolean;
};

/** Détail d'une tentative d'un élève (pour consulter ses réponses). */
export type StudentAttemptDetail = {
  id: number;
  number: number;
  score: number;
  total: number;
  created_at: string;
  answers: StudentAttemptAnswer[];
};

/** Libellé lisible d'une classe, quelle que soit la forme (`name` ou `title`). */
export function classLabel(c: Classroom): string {
  return c.name || c.title || c.code;
}

/** Nom lisible d'un élève, avec repli sur le username si le nom est vide. */
export function studentLabel(s: ClassStudent): string {
  const full = `${s.first_name ?? ''} ${s.last_name ?? ''}`.trim();
  return full || s.username;
}

/** Les classes du caller (côté enseignant : les classes qu'il possède). */
export async function getClasses(): Promise<Classroom[]> {
  const { data } = await api.get<Classroom[]>('/classes/');
  return data;
}

/** Progression de tous les élèves d'une classe (KPIs + évolution des scores). */
export async function getClassProgress(classId: number): Promise<StudentProgress[]> {
  const { data } = await api.get<StudentProgress[]>(`/classes/${classId}/progress/`);
  return data;
}

/** Détail d'une tentative précise d'un élève (réponses corrigées). */
export async function getStudentAttempt(
  classId: number,
  studentId: number,
  attemptId: number,
): Promise<StudentAttemptDetail> {
  const { data } = await api.get<StudentAttemptDetail>(
    `/classes/${classId}/students/${studentId}/attempts/${attemptId}/`,
  );
  return data;
}
