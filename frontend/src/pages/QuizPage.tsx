import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getQuiz, submitAnswers, type Quiz, type AnswerResult } from '@/api/quizzes';

/**
 * Mélange une copie du tableau (Fisher-Yates). Ne mute pas l'entrée.
 * Utilisé par le mode « Refaire mélangé » (Release 2) pour ré-ordonner
 * l'affichage des questions sans toucher aux données du quiz.
 */
function shuffle<T>(items: T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const tmp = out[i]!;
    out[i] = out[j]!;
    out[j] = tmp;
  }
  return out;
}

export default function QuizPage() {
  const { id } = useParams<{ id: string }>();
  const quizId = Number(id);

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  /** Ordre d'affichage des questions (liste d'index). Vide = ordre naturel. */
  const [displayOrder, setDisplayOrder] = useState<number[]>([]);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getQuiz(quizId)
      .then((q) => {
        setQuiz(q);
        setDisplayOrder(q.questions.map((question) => question.index));
      })
      .catch(() => setError('Impossible de charger ce quiz.'))
      .finally(() => setLoading(false));
  }, [quizId]);

  /**
   * Relance une tentative propre en mélangeant l'ordre d'affichage des
   * questions (Fisher-Yates). Réinitialise les réponses et la correction.
   */
  const handleRetestShuffled = () => {
    if (!quiz) return;
    setDisplayOrder(shuffle(quiz.questions.map((q) => q.index)));
    setAnswers({});
    setResult(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSelect = (questionIndex: number, optionIndex: number) => {
    if (result) return; // déjà soumis
    setAnswers((prev) => ({ ...prev, [questionIndex]: optionIndex }));
  };

  const handleSubmit = async () => {
    // Toutes les questions doivent être répondues, quel que soit leur nombre
    // RÉEL (un quiz peut compter 5 à 20 questions, pas forcément 10).
    if (!quiz || Object.keys(answers).length !== quiz.questions.length) return;
    setSubmitting(true);
    try {
      const payload = quiz.questions.map((q) => ({
        index: q.index,
        selected_index: answers[q.index]!,
      }));
      // question_order = ordre d'affichage réel (utile après un « Refaire mélangé »).
      const res = await submitAnswers(quiz.id, payload, displayOrder);
      setResult(res);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      setError('Échec de la soumission.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p className="text-slate-500">Chargement du quiz…</p>;
  if (error) return <p className="text-rose-600">{error}</p>;
  if (!quiz) return null;

  const totalQuestions = quiz.questions.length;
  const allAnswered = Object.keys(answers).length === totalQuestions;

  // Ratio de réussite (0 à 1) calculé sur le total RÉEL renvoyé par l'API :
  // les seuils d'encouragement et de couleur s'adaptent à un quiz de 5 comme
  // de 20 questions (avant : seuils fixes 7/4/10 codés pour 10 questions).
  const scoreRatio = result && result.total > 0 ? result.score / result.total : 0;
  const isPerfect = result !== null && result.score === result.total;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{quiz.title}</h1>
        <p className="text-sm text-slate-500">
          Quiz #{quiz.id} · {quiz.questions.length} questions
        </p>
      </div>

      {/* Résultat */}
      {result && (
        <div
          className={`card border-l-4 ${
            scoreRatio >= 0.7
              ? 'border-emerald-500 bg-emerald-50'
              : scoreRatio >= 0.4
                ? 'border-amber-500 bg-amber-50'
                : 'border-rose-500 bg-rose-50'
          }`}
        >
          <h2 className="text-3xl font-bold text-slate-900 mb-2">
            Score : {result.score} / {result.total}
          </h2>
          <p className="text-slate-700">
            {isPerfect
              ? '🎉 Sans-faute ! Tu maitrises ce chapitre.'
              : scoreRatio >= 0.7
                ? '👍 Bon résultat. Revois les questions ratées en bas de page.'
                : scoreRatio >= 0.4
                  ? "📚 Tu as les bases, mais des révisions s'imposent."
                  : '⚠️ Il faut reprendre le cours en profondeur.'}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={handleRetestShuffled} className="btn-primary">
              🔀 Refaire mélangé
            </button>
            <Link
              to={`/quiz/${quiz.id}/attempts/${result.attempt_id}`}
              className="btn-secondary inline-flex"
            >
              Revoir cette tentative
            </Link>
            <Link to="/history" className="btn-secondary inline-flex">
              Retour à l'historique
            </Link>
          </div>
        </div>
      )}

      {/* Questions (ordre = displayOrder, mélangé après « Refaire mélangé ») */}
      {displayOrder.map((qIndex) => {
        const q = quiz.questions.find((question) => question.index === qIndex);
        if (!q) return null;
        const userChoice = answers[q.index];
        const detail = result?.details.find((d) => d.index === q.index);

        return (
          <article key={q.index} className="card">
            <div className="flex items-baseline gap-2 mb-3">
              <span className="font-mono text-sm text-indigo-600">Q{q.index}</span>
              <h3 className="font-semibold text-slate-900">{q.prompt}</h3>
            </div>
            <div className="space-y-2">
              {q.options.map((opt, optIdx) => {
                const isSelected = userChoice === optIdx;
                const isCorrect = detail && q.correct_index === optIdx;
                const isWrongPick = detail && isSelected && !detail.correct;

                let cls = 'border-slate-200 hover:bg-slate-50';
                if (result) {
                  if (isCorrect) cls = 'border-emerald-500 bg-emerald-50';
                  else if (isWrongPick) cls = 'border-rose-500 bg-rose-50';
                  else cls = 'border-slate-200 opacity-60';
                } else if (isSelected) {
                  cls = 'border-indigo-500 bg-indigo-50';
                }

                return (
                  <button
                    key={optIdx}
                    type="button"
                    disabled={!!result}
                    onClick={() => handleSelect(q.index, optIdx)}
                    className={`w-full text-left p-3 border-2 rounded transition ${cls}`}
                  >
                    <span className="font-mono mr-2 text-slate-500">
                      {String.fromCharCode(65 + optIdx)}.
                    </span>
                    {opt}
                    {result && isCorrect && (
                      <span className="ml-2 text-emerald-600 font-bold">✓</span>
                    )}
                    {result && isWrongPick && (
                      <span className="ml-2 text-rose-600 font-bold">✗</span>
                    )}
                  </button>
                );
              })}
            </div>
          </article>
        );
      })}

      {/* Soumission */}
      {!result && (
        <button
          onClick={handleSubmit}
          disabled={!allAnswered || submitting}
          className="btn-signature w-full py-3 text-base"
        >
          {submitting
            ? 'Correction en cours…'
            : allAnswered
              ? '🎯 Soumettre mes réponses'
              : `Répondre à toutes les questions (${Object.keys(answers).length}/${totalQuestions})`}
        </button>
      )}
    </div>
  );
}
