/**
 * Gabarit commun aux pages légales (Lot 5).
 *
 * [Note pédagogique] Chaque rubrique fournit un `hint` (ce qu'il faut écrire)
 * et un `content` optionnel (le contenu réel rédigé). Tant qu'une rubrique n'a
 * pas de `content`, elle affiche « À compléter — {hint} » et un bandeau ambre
 * invite l'équipe à la rédiger. Une page dont TOUTES les rubriques ont un
 * `content` masque ce bandeau : un site qui collecte des données personnelles
 * DOIT légalement publier ces informations.
 *
 * Pour aider à rédiger, le bandeau (quand il s'affiche) renvoie vers le cours
 * « Réglementation des données » de Mohamed EL AFRIT.
 */
import type { ReactNode } from 'react';

/** URL du cours de référence sur la réglementation des données. */
export const REGLEMENTATION_URL = 'https://mohamedelafrit.com/teaching/Reglementation_des_Donnees';

export type LegalSection = {
  /** Titre de la rubrique (ce que la loi attend de voir). */
  title: string;
  /** Indication pour l'équipe : quoi écrire dans cette rubrique (affichée seulement si `content` absent). */
  hint: string;
  /** Contenu réel de la rubrique. Si présent, remplace le placeholder « À compléter — {hint} ». */
  content?: ReactNode;
};

type Props = {
  title: string;
  intro: string;
  sections: LegalSection[];
  /** Date de dernière mise à jour affichée en pied de page. */
  updatedAt?: string;
  /** Contenu libre optionnel ajouté après les rubriques. */
  children?: ReactNode;
};

export default function LegalScaffold({ title, intro, sections, updatedAt, children }: Props) {
  // Le bandeau « à compléter » ne s'affiche que s'il reste au moins une
  // rubrique sans contenu réel. Une page entièrement rédigée le masque.
  const hasDrafts = sections.some((s) => s.content == null);

  return (
    <article className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-slate-900 mb-2">{title}</h1>
      <p className="text-slate-600 mb-6">{intro}</p>

      {/* Bandeau "à compléter" + lien vers le cours de référence */}
      {hasDrafts && (
        <div className="mb-8 p-4 bg-amber-50 border-l-4 border-amber-400 rounded text-sm text-amber-900">
          <p className="font-semibold mb-1">📝 Page à compléter par votre équipe</p>
          <p>
            Certaines rubriques restent à rédiger. Remplacez chaque indication en italique par le
            contenu réel de votre projet. Besoin d'aide ?{' '}
            <a
              href={REGLEMENTATION_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-700 underline hover:no-underline font-medium"
            >
              Consultez le cours « Réglementation des données »
            </a>
            .
          </p>
        </div>
      )}

      <div className="space-y-6">
        {sections.map((section, i) => (
          <section key={section.title}>
            <h2 className="text-lg font-semibold text-slate-900 mb-1">
              {i + 1}. {section.title}
            </h2>
            {section.content != null ? (
              <div className="text-sm text-slate-700 space-y-2">{section.content}</div>
            ) : (
              <p className="text-sm text-slate-500 italic">À compléter — {section.hint}</p>
            )}
          </section>
        ))}
      </div>

      {children}

      <p className="text-xs text-slate-400 mt-10 pt-4 border-t border-slate-200">
        Dernière mise à jour : <em>{updatedAt ?? 'à compléter'}</em>. Document rédigé dans le cadre
        pédagogique APOCAL'IPSSI 2026.
      </p>
    </article>
  );
}
