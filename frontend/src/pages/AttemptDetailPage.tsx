/**
 * Détail d'une tentative (Release 2).
 *
 * Rejoue une tentative passée d'un quiz avec les corrections : chaque question
 * montre la BONNE réponse (en vert via correct_index), la réponse de
 * l'utilisateur, et un statut correct / incorrect (is_correct). Lecture seule.
 */
import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAttemptDetail, type AttemptDetail } from '@/api/quizzes';
import { getApiErrorMessage } from '@/api/errors';

export default function AttemptDetailPage() {
  const { id, attemptId } = useParams<{ id: string; attemptId: string }>();
  const quizId = Number(id);
  const attemptPk = Number(attemptId);

  const [attempt, setAttempt] = useState<AttemptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAttemptDetail(quizId, attemptPk)
      .then(setAttempt)
      .catch((err) => setError(getApiErrorMessage(err, 'Impossible de charger cette tentative.')))
      .finally(() => setLoading(false));
  }, [quizId, attemptPk]);

  if (loading) return <p className="text-slate-500">Chargement de la tentative…</p>;
  if (error) return <p className="text-rose-600">{error}</p>;
  if (!attempt) return null;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* En-tête + score */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Tentative #{attempt.number}</h1>
        <p className="text-sm text-slate-500">
          Quiz #{quizId} · {new Date(attempt.created_at).toLocaleString('fr-FR')}
        </p>
      </div>

      <div
        className={`card border-l-4 ${
          attempt.score >= 7
            ? 'border-emerald-500 bg-emerald-50'
            : attempt.score >= 4
              ? 'border-amber-500 bg-amber-50'
              : 'border-rose-500 bg-rose-50'
        }`}
      >
        <h2 className="text-3xl font-bold text-slate-900 mb-2">
          Score : {attempt.score} / {attempt.total}
        </h2>
        <div className="flex flex-wrap gap-3 mt-2">
          <Link to={`/quiz/${quizId}`} className="btn-primary inline-flex">
            🔁 Repasser ce quiz
          </Link>
          <Link to="/history" className="btn-secondary inline-flex">
            Retour à l'historique
          </Link>
        </div>
      </div>

      {/* Réponses rejouées avec corrections */}
      {attempt.answers.map((a) => (
        <article key={a.index} className="card">
          <div className="flex items-baseline gap-2 mb-3">
            <span className="font-mono text-sm text-indigo-600">Q{a.index}</span>
            <h3 className="font-semibold text-slate-900">{a.prompt}</h3>
            <span
              className={`ml-auto text-xs font-semibold whitespace-nowrap ${
                a.is_correct ? 'text-emerald-600' : 'text-rose-600'
              }`}
            >
              {a.is_correct ? '✓ Correct' : '✗ Incorrect'}
            </span>
          </div>
          <div className="space-y-2">
            {a.options.map((opt, optIdx) => {
              const isCorrect = a.correct_index === optIdx;
              const isSelected = a.selected_index === optIdx;
              const isWrongPick = isSelected && !a.is_correct;

              let cls = 'border-slate-200 opacity-60';
              if (isCorrect) cls = 'border-emerald-500 bg-emerald-50';
              else if (isWrongPick) cls = 'border-rose-500 bg-rose-50';

              return (
                <div key={optIdx} className={`w-full text-left p-3 border-2 rounded ${cls}`}>
                  <span className="font-mono mr-2 text-slate-500">
                    {String.fromCharCode(65 + optIdx)}.
                  </span>
                  {opt}
                  {isCorrect && <span className="ml-2 text-emerald-600 font-bold">✓</span>}
                  {isWrongPick && <span className="ml-2 text-rose-600 font-bold">✗</span>}
                </div>
              );
            })}
          </div>
        </article>
      ))}
    </div>
  );
}
