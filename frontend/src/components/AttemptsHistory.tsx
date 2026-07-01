/**
 * Historique des tentatives (Release 2).
 *
 * Affiche, pour chaque quiz (« cours »), l'ensemble de ses tentatives sous
 * forme de barres verticales (score /10). Une rangée d'ONGLETS permet de
 * basculer d'un quiz à l'autre. Le graphique est dessiné « à la main » avec de
 * simples <div>, dans le même esprit que le dashboard (pas de librairie de
 * charting), pour rester cohérent avec le style « maison » du projet.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAttempts, type Attempt, type QuizSummary } from '@/api/quizzes';
import { getApiErrorMessage } from '@/api/errors';

/** Couleur d'une barre selon le score (vert / ambre / rouge) — repris du dashboard. */
function barColor(score: number): string {
  if (score >= 7) return 'bg-emerald-500';
  if (score >= 4) return 'bg-amber-500';
  return 'bg-rose-500';
}

/** Barres des tentatives d'un quiz donné (les plus anciennes à gauche). */
function AttemptBars({ quizId, attempts }: { quizId: number; attempts: Attempt[] }) {
  // L'API renvoie les plus récentes d'abord ; on les remet dans l'ordre
  // chronologique pour lire la progression de gauche à droite.
  const chrono = [...attempts].reverse();

  if (chrono.length === 0) {
    return <p className="text-sm text-slate-500">Aucune tentative pour ce quiz pour l'instant.</p>;
  }

  return (
    <>
      <div className="flex items-end gap-2 h-48 border-b border-l border-slate-200 pl-2 pb-px">
        {chrono.map((a) => (
          <Link
            key={a.id}
            to={`/quiz/${quizId}/attempts/${a.id}`}
            className="flex-1 flex flex-col items-center justify-end h-full group"
            title={`Tentative #${a.number} — ${a.score}/${a.total} (${new Date(
              a.created_at,
            ).toLocaleDateString('fr-FR')})`}
            aria-label={`Tentative #${a.number} — ${a.score}/${a.total}`}
          >
            <span className="text-xs text-slate-500 mb-1">{a.score}</span>
            <div
              className={`w-full rounded-t ${barColor(a.score)} transition-all group-hover:opacity-80`}
              style={{ height: `${(a.score / (a.total || 10)) * 100}%` }}
            />
            <span className="text-[10px] text-slate-400 mt-1">#{a.number}</span>
          </Link>
        ))}
      </div>
      <p className="text-xs text-slate-400 mt-2">
        Chaque barre = une tentative (score /{chrono[0]?.total ?? 10}), dans l'ordre chronologique.
        Cliquez pour rejouer une tentative avec les corrections.
      </p>
    </>
  );
}

/**
 * Composant réutilisable : onglets par quiz + barres des tentatives.
 * `quizzes` : la liste des quiz passés (utilisée pour les onglets/titres).
 */
export default function AttemptsHistory({ quizzes }: { quizzes: QuizSummary[] }) {
  const [activeQuizId, setActiveQuizId] = useState<number | null>(quizzes[0]?.id ?? null);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Si le quiz actif n'est plus dans la liste (ou liste vide), on se recale.
    if (activeQuizId === null || !quizzes.some((q) => q.id === activeQuizId)) {
      setActiveQuizId(quizzes[0]?.id ?? null);
    }
  }, [quizzes, activeQuizId]);

  useEffect(() => {
    if (activeQuizId === null) {
      setAttempts([]);
      return;
    }
    setLoading(true);
    setError(null);
    getAttempts(activeQuizId)
      .then(setAttempts)
      .catch((err) => setError(getApiErrorMessage(err, 'Impossible de charger les tentatives.')))
      .finally(() => setLoading(false));
  }, [activeQuizId]);

  if (quizzes.length === 0) {
    return (
      <div className="card text-center py-12">
        <div className="text-5xl mb-4">📊</div>
        <p className="text-slate-600 mb-4">
          Aucune tentative pour l'instant. Passez un quiz pour voir vos tentatives ici.
        </p>
        <Link to="/upload" className="btn-primary">
          Créer un quiz
        </Link>
      </div>
    );
  }

  const activeQuiz = quizzes.find((q) => q.id === activeQuizId) ?? null;

  return (
    <div className="space-y-4">
      {/* Onglets — un par quiz / « cours » */}
      <div className="flex gap-2 flex-wrap border-b border-slate-200">
        {quizzes.map((q) => {
          const isActive = q.id === activeQuizId;
          return (
            <button
              key={q.id}
              type="button"
              onClick={() => setActiveQuizId(q.id)}
              className={`px-3 py-2 text-sm font-medium -mb-px border-b-2 transition ${
                isActive
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {q.title}
            </button>
          );
        })}
      </div>

      {/* Contenu de l'onglet actif */}
      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-slate-900">
            {activeQuiz ? activeQuiz.title : 'Tentatives'}
          </h2>
          {activeQuizId !== null && (
            <Link to={`/quiz/${activeQuizId}`} className="text-sm text-indigo-600 hover:underline">
              Repasser ce quiz →
            </Link>
          )}
        </div>

        {loading ? (
          <p className="text-slate-500">Chargement des tentatives…</p>
        ) : error ? (
          <p className="text-rose-600">{error}</p>
        ) : (
          activeQuizId !== null && <AttemptBars quizId={activeQuizId} attempts={attempts} />
        )}
      </div>
    </div>
  );
}
