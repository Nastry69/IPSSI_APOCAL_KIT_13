/**
 * Espace prof (Release 2 — Feature #3).
 *
 * Page réservée aux enseignants pour suivre leurs élèves :
 *   - sélection d'une classe (onglets, depuis getClasses) ;
 *   - recherche d'un élève par nom / username ;
 *   - pour chaque élève : KPIs (quiz passés, moyenne, meilleur score) + un
 *     graphe d'évolution des scores (barres « maison », comme le dashboard) ;
 *   - clic sur une barre / tentative → affiche les RÉPONSES de l'élève pour
 *     cette tentative (bonne réponse en vert, réponse choisie, statut).
 *
 * Le graphique est dessiné « à la main » avec de simples <div> pour rester
 * cohérent avec le style « maison » du projet (dashboard, historique).
 */
import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getApiErrorMessage } from '@/api/errors';
import {
  getClasses,
  getClassProgress,
  getStudentAttempt,
  classLabel,
  studentLabel,
  type Classroom,
  type StudentProgress,
  type EvolutionPoint,
  type StudentAttemptDetail,
} from '@/api/classes';

/** Couleur d'une barre selon le score /10 — repris du dashboard. */
function barColor(score: number, total: number): string {
  const pct = total ? (score / total) * 10 : 0;
  if (pct >= 7) return 'bg-emerald-500';
  if (pct >= 4) return 'bg-amber-500';
  return 'bg-rose-500';
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

/**
 * Détail des réponses d'une tentative précise d'un élève.
 * Chargé à la demande (quand l'enseignant clique sur une barre).
 */
function AttemptAnswers({
  classId,
  studentId,
  attempt,
}: {
  classId: number;
  studentId: number;
  attempt: EvolutionPoint;
}) {
  const [detail, setDetail] = useState<StudentAttemptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    getStudentAttempt(classId, studentId, attempt.attempt_id)
      .then((d) => alive && setDetail(d))
      .catch(
        (err) =>
          alive && setError(getApiErrorMessage(err, 'Impossible de charger cette tentative.')),
      )
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [classId, studentId, attempt.attempt_id]);

  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4">
      <h4 className="font-semibold text-slate-900 mb-3">
        {attempt.quiz_title} — tentative #{attempt.number} ({attempt.score}/{attempt.total})
      </h4>

      {loading ? (
        <p className="text-slate-500 text-sm">Chargement des réponses…</p>
      ) : error ? (
        <p className="text-rose-600 text-sm">{error}</p>
      ) : detail ? (
        <div className="space-y-4">
          {detail.answers.map((a) => (
            <article key={a.index} className="rounded border border-slate-200 bg-white p-3">
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-mono text-sm text-indigo-600">Q{a.index}</span>
                <h5 className="font-medium text-slate-900">{a.prompt}</h5>
                <span
                  className={`ml-auto text-xs font-semibold whitespace-nowrap ${
                    a.is_correct ? 'text-emerald-600' : 'text-rose-600'
                  }`}
                >
                  {a.is_correct ? '✓ Correct' : '✗ Incorrect'}
                </span>
              </div>
              <div className="space-y-1.5">
                {a.options.map((opt, optIdx) => {
                  const isCorrect = a.correct_index === optIdx;
                  const isSelected = a.selected_index === optIdx;
                  const isWrongPick = isSelected && !a.is_correct;

                  let cls = 'border-slate-200 opacity-60';
                  if (isCorrect) cls = 'border-emerald-500 bg-emerald-50';
                  else if (isWrongPick) cls = 'border-rose-500 bg-rose-50';

                  return (
                    <div key={optIdx} className={`text-left p-2 border rounded text-sm ${cls}`}>
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
      ) : null}
    </div>
  );
}

/** Carte d'un élève : nom + KPIs + graphe d'évolution + détail dépliable. */
function StudentCard({ classId, progress }: { classId: number; progress: StudentProgress }) {
  const [openAttempt, setOpenAttempt] = useState<EvolutionPoint | null>(null);

  // L'évolution est censée arriver dans l'ordre chronologique ; on sécurise le
  // tri pour lire la progression de gauche à droite.
  const chrono = useMemo(
    () => [...progress.evolution].sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [progress.evolution],
  );

  return (
    <div className="card">
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h3 className="text-lg font-semibold text-slate-900">{studentLabel(progress.student)}</h3>
        <div className="grid grid-cols-3 gap-2">
          <KpiCard label="Quiz passés" value={String(progress.quizzes_taken)} />
          <KpiCard
            label="Moyenne"
            value={progress.average_score !== null ? `${progress.average_score}/10` : '—'}
          />
          <KpiCard
            label="Meilleur"
            value={progress.best_score !== null ? `${progress.best_score}/10` : '—'}
          />
        </div>
      </div>

      {chrono.length === 0 ? (
        <p className="text-sm text-slate-500">Cet élève n'a encore passé aucun quiz.</p>
      ) : (
        <>
          <div className="flex items-end gap-2 h-40 border-b border-l border-slate-200 pl-2 pb-px">
            {chrono.map((e) => {
              const isOpen = openAttempt?.attempt_id === e.attempt_id;
              return (
                <button
                  key={e.attempt_id}
                  type="button"
                  onClick={() => setOpenAttempt(isOpen ? null : e)}
                  className="flex-1 flex flex-col items-center justify-end h-full group"
                  title={`${e.quiz_title} — tentative #${e.number} : ${e.score}/${e.total} (${new Date(
                    e.created_at,
                  ).toLocaleDateString('fr-FR')})`}
                  aria-label={`Voir les réponses — ${e.quiz_title} tentative #${e.number} : ${e.score}/${e.total}`}
                >
                  <span className="text-xs text-slate-500 mb-1">{e.score}</span>
                  <div
                    className={`w-full rounded-t ${barColor(e.score, e.total)} transition-all group-hover:opacity-80 ${
                      isOpen ? 'ring-2 ring-indigo-400' : ''
                    }`}
                    style={{ height: `${e.total ? (e.score / e.total) * 100 : 0}%` }}
                  />
                  <span className="text-[10px] text-slate-400 mt-1">#{e.number}</span>
                </button>
              );
            })}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Chaque barre = une tentative, dans l'ordre chronologique. Cliquez sur une barre pour
            voir les réponses de l'élève.
          </p>

          {openAttempt && (
            <AttemptAnswers
              classId={classId}
              studentId={progress.student.id}
              attempt={openAttempt}
            />
          )}
        </>
      )}
    </div>
  );
}

export default function TeacherPage() {
  const { user } = useAuth();

  const [classes, setClasses] = useState<Classroom[]>([]);
  const [activeClassId, setActiveClassId] = useState<number | null>(null);
  const [progress, setProgress] = useState<StudentProgress[]>([]);
  const [search, setSearch] = useState('');

  const [loadingClasses, setLoadingClasses] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isTeacher = user?.role === 'teacher';

  // Chargement des classes (seulement si enseignant).
  useEffect(() => {
    if (!isTeacher) return;
    setLoadingClasses(true);
    getClasses()
      .then((list) => {
        setClasses(list);
        setActiveClassId((prev) => prev ?? list[0]?.id ?? null);
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Impossible de charger vos classes.')))
      .finally(() => setLoadingClasses(false));
  }, [isTeacher]);

  // Chargement de la progression de la classe active.
  useEffect(() => {
    if (!isTeacher || activeClassId === null) {
      setProgress([]);
      return;
    }
    setLoadingProgress(true);
    setError(null);
    getClassProgress(activeClassId)
      .then(setProgress)
      .catch((err) =>
        setError(getApiErrorMessage(err, 'Impossible de charger la progression de la classe.')),
      )
      .finally(() => setLoadingProgress(false));
  }, [isTeacher, activeClassId]);

  // Filtre de recherche : par nom, prénom ou username (insensible à la casse).
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return progress;
    return progress.filter((p) => {
      const s = p.student;
      const haystack = `${s.first_name} ${s.last_name} ${s.username}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [progress, search]);

  // Gating par rôle : réservé aux enseignants.
  if (!isTeacher) {
    return (
      <div className="card text-center py-12">
        <div className="text-5xl mb-4">🔒</div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Espace réservé aux enseignants</h1>
        <p className="text-slate-600">
          Cette page permet de suivre la progression des élèves. Elle n'est accessible qu'aux
          comptes enseignants.
        </p>
      </div>
    );
  }

  const activeClass = classes.find((c) => c.id === activeClassId) ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Espace prof</h1>
        <p className="text-slate-500 text-sm">
          Suivez la progression de vos élèves, classe par classe.
        </p>
      </div>

      {loadingClasses ? (
        <p className="text-slate-500">Chargement de vos classes…</p>
      ) : classes.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-5xl mb-4">🏫</div>
          <p className="text-slate-600">
            Vous n'avez aucune classe pour l'instant. Créez une classe et partagez son code
            d'invitation à vos élèves pour commencer à suivre leur progression.
          </p>
        </div>
      ) : (
        <>
          {/* Onglets — une classe par onglet */}
          <div className="flex gap-2 flex-wrap border-b border-slate-200">
            {classes.map((c) => {
              const isActive = c.id === activeClassId;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setActiveClassId(c.id)}
                  className={`px-3 py-2 text-sm font-medium -mb-px border-b-2 transition ${
                    isActive
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {classLabel(c)}
                  <span className="ml-1 text-xs text-slate-400">({c.student_count})</span>
                </button>
              );
            })}
          </div>

          {/* Barre de recherche d'un élève */}
          <div>
            <label htmlFor="student-search" className="sr-only">
              Rechercher un élève
            </label>
            <input
              id="student-search"
              type="search"
              className="input"
              placeholder="Rechercher un élève par nom ou identifiant…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {error && <p className="text-rose-600">{error}</p>}

          {loadingProgress ? (
            <p className="text-slate-500">Chargement de la progression…</p>
          ) : progress.length === 0 ? (
            <div className="card text-center py-10 text-slate-600">
              {activeClass
                ? `Aucun élève dans « ${classLabel(activeClass)} » pour l'instant.`
                : null}
            </div>
          ) : filtered.length === 0 ? (
            <div className="card text-center py-10 text-slate-600">
              Aucun élève ne correspond à « {search} ».
            </div>
          ) : (
            <div className="space-y-4">
              {filtered.map((p) => (
                <StudentCard key={p.student.id} classId={activeClassId as number} progress={p} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
