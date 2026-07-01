/**
 * Hub de révision (Release 3 — Feature F1).
 *
 * Permet à l'étudiant de retrouver et de ROUVRIR ce qu'il a déjà produit :
 *   - ses QCM (depuis `GET /quizzes/`),
 *   - ses fiches de révision (study-docs kind=note),
 *   - ses résumés (study-docs kind=summary).
 *
 * Un simple menu déroulant (select) à 3 choix pilote la liste affichée. Chaque
 * item est cliquable pour rouvrir la ressource : QCM → /quiz/:id, fiche/résumé
 * → /study/:id. Tout est déjà persisté en BDD : cette page ne fait que lister.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listQuizzes, type QuizSummary } from '@/api/quizzes';
import { listStudyDocs, type StudyDocSummary } from '@/api/llm';
import { getApiErrorMessage } from '@/api/errors';

/** Les trois catégories révisables, telles que présentées dans le select. */
type Category = 'quiz' | 'note' | 'summary';

const CATEGORY_LABEL: Record<Category, string> = {
  quiz: 'QCM',
  note: 'Fiche de révision',
  summary: 'Résumé',
};

/** Formate une date ISO en date courte française. */
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR');
}

export default function ReviewHubPage() {
  const [category, setCategory] = useState<Category>('quiz');
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [docs, setDocs] = useState<StudyDocSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // On charge les deux sources une seule fois : le select ne fait que filtrer.
  useEffect(() => {
    Promise.all([listQuizzes(), listStudyDocs()])
      .then(([quizzesRes, docsRes]) => {
        setQuizzes(quizzesRes.results);
        setDocs(docsRes);
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Impossible de charger vos révisions.')))
      .finally(() => setLoading(false));
  }, []);

  // Fiches et résumés partagent la même source : on filtre par `kind`.
  const notes = docs.filter((d) => d.kind === 'note');
  const summaries = docs.filter((d) => d.kind === 'summary');

  /** Nombre d'éléments de la catégorie courante (pour le sous-titre). */
  const count =
    category === 'quiz' ? quizzes.length : category === 'note' ? notes.length : summaries.length;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Réviser</h1>
          <p className="text-slate-500 text-sm">
            Retrouvez et rouvrez vos QCM, fiches de révision et résumés.
          </p>
        </div>
        <Link to="/upload" className="btn-primary">
          + Nouveau document
        </Link>
      </div>

      {/* Sélecteur de catégorie */}
      <div className="card">
        <label htmlFor="review-category" className="block text-sm font-medium text-slate-700 mb-2">
          Que souhaitez-vous revoir ?
        </label>
        <select
          id="review-category"
          value={category}
          onChange={(e) => setCategory(e.target.value as Category)}
          className="input"
        >
          <option value="quiz">{CATEGORY_LABEL.quiz}</option>
          <option value="note">{CATEGORY_LABEL.note}</option>
          <option value="summary">{CATEGORY_LABEL.summary}</option>
        </select>
        {!loading && !error && (
          <p className="text-xs text-slate-400 mt-2">
            {count === 0
              ? `Aucun élément dans « ${CATEGORY_LABEL[category]} » pour l'instant.`
              : `${count} élément${count > 1 ? 's' : ''} dans « ${CATEGORY_LABEL[category]} ».`}
          </p>
        )}
      </div>

      {loading && <p className="text-slate-500">Chargement…</p>}
      {error && <p className="text-rose-600">{error}</p>}

      {!loading && !error && (
        <>
          {category === 'quiz' && <QuizList quizzes={quizzes} />}
          {category === 'note' && <StudyDocList docs={notes} kind="note" />}
          {category === 'summary' && <StudyDocList docs={summaries} kind="summary" />}
        </>
      )}
    </div>
  );
}

/** Liste des QCM. Chaque carte rouvre le quiz (/quiz/:id). */
function QuizList({ quizzes }: { quizzes: QuizSummary[] }) {
  if (quizzes.length === 0) {
    return (
      <div className="card text-center py-12">
        <div className="text-5xl mb-4">📝</div>
        <p className="text-slate-600 mb-4">Vous n'avez pas encore de QCM.</p>
        <Link to="/upload" className="btn-primary">
          Créer un QCM
        </Link>
      </div>
    );
  }

  return (
    <div className="grid sm:grid-cols-2 gap-4">
      {quizzes.map((q) => (
        <Link
          key={q.id}
          to={`/quiz/${q.id}`}
          className="card hover:border-indigo-500 hover:shadow-md transition"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-xs text-slate-500">
              #{q.id} · {formatDate(q.created_at)}
            </span>
            {q.score !== null ? (
              <span
                className={`px-2 py-0.5 rounded font-mono text-sm font-bold ${
                  q.score >= 7
                    ? 'bg-emerald-100 text-emerald-700'
                    : q.score >= 4
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-rose-100 text-rose-700'
                }`}
              >
                {q.score} / {q.nb_questions}
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-mono">
                pas encore passé
              </span>
            )}
          </div>
          <h3 className="font-semibold text-slate-900 mb-1">{q.title}</h3>
          <p className="text-sm text-slate-500">{q.nb_questions} questions</p>
        </Link>
      ))}
    </div>
  );
}

/** Liste des fiches de révision ou des résumés. Chaque carte rouvre /study/:id. */
function StudyDocList({ docs, kind }: { docs: StudyDocSummary[]; kind: 'note' | 'summary' }) {
  if (docs.length === 0) {
    const label = kind === 'note' ? 'fiche de révision' : 'résumé';
    return (
      <div className="card text-center py-12">
        <div className="text-5xl mb-4">{kind === 'note' ? '📕' : '📄'}</div>
        <p className="text-slate-600 mb-4">Vous n'avez pas encore de {label}.</p>
        <Link to="/upload" className="btn-primary">
          Générer un document
        </Link>
      </div>
    );
  }

  return (
    <div className="grid sm:grid-cols-2 gap-4">
      {docs.map((d) => (
        <Link
          key={d.id}
          to={`/study/${d.id}`}
          className="card hover:border-indigo-500 hover:shadow-md transition"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-xs text-slate-500">
              #{d.id} · {formatDate(d.created_at)}
            </span>
            <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 text-xs font-medium">
              {kind === 'note' ? 'Fiche' : 'Résumé'}
            </span>
          </div>
          <h3 className="font-semibold text-slate-900">{d.title}</h3>
        </Link>
      ))}
    </div>
  );
}
