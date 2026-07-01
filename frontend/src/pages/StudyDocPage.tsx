import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getStudyDoc, type StudyDoc } from '@/api/llm';

/** Libellé lisible du type de document d'étude. */
const KIND_LABEL: Record<StudyDoc['kind'], string> = {
  note: 'Fiche de révision',
  summary: 'Résumé',
};

/**
 * Affiche un document d'étude (fiche de révision ou résumé) généré par le LLM.
 * Release 2 — Feature #1. Le `content` est du texte/markdown : on le rend
 * lisiblement avec `whitespace-pre-wrap` (pas de lib markdown nécessaire).
 */
export default function StudyDocPage() {
  const { id } = useParams<{ id: string }>();
  const docId = Number(id);

  const [doc, setDoc] = useState<StudyDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getStudyDoc(docId)
      .then(setDoc)
      .catch(() => setError('Impossible de charger ce document.'))
      .finally(() => setLoading(false));
  }, [docId]);

  if (loading) return <p className="text-slate-500">Chargement du document…</p>;
  if (error) return <p className="text-rose-600">{error}</p>;
  if (!doc) return null;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* En-tête */}
      <div>
        <p className="text-sm font-medium text-indigo-600">{KIND_LABEL[doc.kind]}</p>
        <h1 className="text-2xl font-bold text-slate-900">{doc.title}</h1>
      </div>

      {/* Contenu texte/markdown rendu tel quel (retours à la ligne préservés). */}
      <article className="card">
        <p className="whitespace-pre-wrap text-slate-800 leading-relaxed">{doc.content}</p>
      </article>

      <div className="flex flex-wrap gap-3">
        <Link to="/upload" className="btn-secondary inline-flex">
          Générer un autre document
        </Link>
        <Link to="/history" className="btn-secondary inline-flex">
          Retour à l'historique
        </Link>
      </div>
    </div>
  );
}
