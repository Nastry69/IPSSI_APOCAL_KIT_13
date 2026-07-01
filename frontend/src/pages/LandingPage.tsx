import { Link } from 'react-router-dom';

/**
 * Landing page marketing (page de garde publique).
 *
 * Affichée sur la route index "/" pour les visiteurs NON connectés (voir
 * HomePage.tsx qui délègue ici). Objectif : convaincre en quelques secondes
 * (élève OU enseignant) et pousser vers l'inscription.
 *
 * Conventions respectées : classes utilitaires du design system existant
 * (.btn-primary/.btn-secondary/.card dans src/index.css), palette
 * indigo/amber, dark mode via les variantes `dark:` + rétrofit slate global.
 */
export default function LandingPage() {
  return (
    <div className="space-y-20 md:space-y-28">
      {/* HERO */}
      <section className="text-center pt-6 pb-4 md:pt-12">
        <span
          className="inline-block mb-4 px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase
                     bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
        >
          Propulsé par l'IA · 100% local
        </span>

        <h1 className="text-4xl md:text-6xl font-bold text-slate-900 leading-tight max-w-4xl mx-auto">
          Transformer n'importe quel cours en{' '}
          <span className="bg-gradient-to-r from-indigo-600 to-amber-500 bg-clip-text text-transparent">
            quiz, fiche ou résumé personnalisé
          </span>{' '}
          en moins de 5 minutes, pour réviser ou enseigner.
        </h1>

        <p className="mt-6 text-lg md:text-xl text-slate-600 max-w-2xl mx-auto">
          Dépose ton support de cours, choisis ton format et ton niveau : EduTutor IA génère du
          contenu pédagogique prêt à l'emploi, en quelques clics.
        </p>

        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          <Link
            to="/signup"
            aria-label="Créer mon compte gratuitement"
            className="btn-primary px-6 py-3 text-base"
          >
            Créer mon compte gratuitement
          </Link>
          <Link
            to="/login"
            aria-label="Se connecter à mon compte existant"
            className="btn-secondary px-6 py-3 text-base"
          >
            Se connecter
          </Link>
        </div>

        <p className="mt-4 text-xs text-slate-500">
          Sans carte bancaire. Résiliable à tout moment.
        </p>
      </section>

      {/* DOUBLE CIBLE : Élève / Enseignant */}
      <section aria-labelledby="cibles-heading" className="space-y-8">
        <div className="text-center max-w-2xl mx-auto">
          <h2 id="cibles-heading" className="text-2xl md:text-3xl font-bold text-slate-900 mb-3">
            Que tu sois élève ou enseignant
          </h2>
          <p className="text-slate-600">
            EduTutor IA s'adapte à ton usage : réviser plus vite, ou préparer et suivre ta classe
            sans perdre de temps.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="card border-t-4 border-t-indigo-600 flex flex-col">
            <div className="text-3xl mb-3" aria-hidden="true">
              🎓
            </div>
            <h3 className="font-semibold text-lg text-slate-900 mb-2">Je suis élève / étudiant</h3>
            <p className="text-sm mb-4">
              Transforme un cours en QCM pour t'auto-évaluer, ou en fiche de révision condensée
              avant un contrôle. Suis ta progression et identifie tes lacunes.
            </p>
            <ul className="text-sm space-y-2 mb-5">
              <li className="flex items-start gap-2">
                <CheckIcon />
                <span>Quiz générés en quelques secondes</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckIcon />
                <span>Fiches de révision synthétiques</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckIcon />
                <span>Historique et suivi de tes scores</span>
              </li>
            </ul>
            <Link
              to="/signup"
              aria-label="Créer mon compte pour réviser"
              className="btn-primary mt-auto self-start"
            >
              Réviser maintenant
            </Link>
          </div>

          <div className="card border-t-4 border-t-amber-500 flex flex-col">
            <div className="text-3xl mb-3" aria-hidden="true">
              🧑‍🏫
            </div>
            <h3 className="font-semibold text-lg text-slate-900 mb-2">Je suis enseignant</h3>
            <p className="text-sm mb-4">
              Génère des quiz ou des résumés à partir de tes supports de cours, distribue-les à ta
              classe et gagne un temps précieux sur la préparation.
            </p>
            <ul className="text-sm space-y-2 mb-5">
              <li className="flex items-start gap-2">
                <CheckIcon />
                <span>Quiz prêts à distribuer en un clic</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckIcon />
                <span>Adaptation automatique au niveau visé</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckIcon />
                <span>Suivi des résultats de la classe</span>
              </li>
            </ul>
            <Link
              to="/signup"
              aria-label="Créer mon compte pour enseigner"
              className="btn-signature mt-auto self-start"
            >
              Créer des quiz
            </Link>
          </div>
        </div>
      </section>

      {/* 3 FORMATS */}
      <section aria-labelledby="formats-heading" className="space-y-8">
        <div className="text-center max-w-2xl mx-auto">
          <h2 id="formats-heading" className="text-2xl md:text-3xl font-bold text-slate-900 mb-3">
            3 formats, un seul cours
          </h2>
          <p className="text-slate-600">
            Choisis le format le plus adapté à ton objectif du moment.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="card text-center">
            <div className="text-3xl mb-3" aria-hidden="true">
              📝
            </div>
            <h3 className="font-semibold text-slate-900 mb-2">Quiz</h3>
            <p className="text-sm">
              Des questions à choix multiples générées automatiquement pour tester tes connaissances
              et t'auto-corriger instantanément.
            </p>
          </div>
          <div className="card text-center">
            <div className="text-3xl mb-3" aria-hidden="true">
              📋
            </div>
            <h3 className="font-semibold text-slate-900 mb-2">Fiche de révision</h3>
            <p className="text-sm">
              Une synthèse structurée des points clés du cours, idéale pour réviser rapidement avant
              un examen.
            </p>
          </div>
          <div className="card text-center">
            <div className="text-3xl mb-3" aria-hidden="true">
              📄
            </div>
            <h3 className="font-semibold text-slate-900 mb-2">Résumé</h3>
            <p className="text-sm">
              Une version condensée et claire du contenu, pour saisir l'essentiel sans relire tout
              le cours.
            </p>
          </div>
        </div>
      </section>

      {/* COMMENT ÇA MARCHE */}
      <section aria-labelledby="comment-heading" className="space-y-8">
        <div className="text-center max-w-2xl mx-auto">
          <h2 id="comment-heading" className="text-2xl md:text-3xl font-bold text-slate-900 mb-3">
            Comment ça marche
          </h2>
          <p className="text-slate-600">Trois étapes, moins de 5 minutes.</p>
        </div>

        <ol className="grid md:grid-cols-3 gap-6">
          <li className="card relative pt-8">
            <StepBadge n={1} />
            <h3 className="font-semibold text-slate-900 mb-2">Déposer un cours</h3>
            <p className="text-sm">
              Upload un PDF (≤ 5 Mo) ou colle directement ton texte de cours.
            </p>
          </li>
          <li className="card relative pt-8">
            <StepBadge n={2} />
            <h3 className="font-semibold text-slate-900 mb-2">Choisir le format et le niveau</h3>
            <p className="text-sm">Quiz, fiche ou résumé — adapté au niveau visé.</p>
          </li>
          <li className="card relative pt-8">
            <StepBadge n={3} />
            <h3 className="font-semibold text-slate-900 mb-2">Réviser / distribuer à la classe</h3>
            <p className="text-sm">
              Consulte ton contenu généré, révise seul ou partage-le avec ta classe.
            </p>
          </li>
        </ol>
      </section>

      {/* CTA FINAL */}
      <section className="text-center card bg-gradient-to-br from-indigo-600 to-indigo-950 border-none py-12 px-6">
        <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
          Prêt à gagner du temps sur tes révisions ou tes cours ?
        </h2>
        <p className="text-indigo-100 max-w-xl mx-auto mb-6">
          Rejoins EduTutor IA gratuitement et génère ton premier quiz, fiche ou résumé en moins de 5
          minutes.
        </p>
        <div className="flex flex-wrap gap-3 justify-center">
          <Link
            to="/signup"
            aria-label="Créer mon compte gratuitement"
            className="btn bg-amber-500 text-slate-900 hover:bg-amber-600 px-6 py-3 text-base"
          >
            Créer mon compte gratuitement
          </Link>
          <Link
            to="/login"
            aria-label="Se connecter à mon compte existant"
            className="btn bg-white/10 text-white border border-white/30 hover:bg-white/20 px-6 py-3 text-base"
          >
            Se connecter
          </Link>
        </div>
      </section>
    </div>
  );
}

/** Petite coche décorative (SVG inline, pas de dépendance d'icônes). */
function CheckIcon() {
  return (
    <svg
      className="w-5 h-5 flex-shrink-0 text-emerald-500 mt-0.5"
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
        clipRule="evenodd"
      />
    </svg>
  );
}

/** Pastille numérotée pour la section "Comment ça marche". */
function StepBadge({ n }: { n: number }) {
  return (
    <span
      className="absolute -top-4 left-6 w-8 h-8 grid place-items-center rounded-full bg-indigo-600
                 text-white font-bold text-sm shadow-sm"
      aria-hidden="true"
    >
      {n}
    </span>
  );
}
