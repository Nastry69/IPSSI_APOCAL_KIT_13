import { useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { generateQuiz } from '@/api/llm';
import { getApiErrorMessage } from '@/api/errors';

// Garde-fou taille PDF côté client : aligné sur le backend (pdf_utils rejette > 5 Mo).
// On évite ainsi un upload inutile (parfois plusieurs Mo) voué à être refusé.
const MAX_PDF_SIZE = 5 * 1024 * 1024; // 5 Mo

export default function UploadPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [mode, setMode] = useState<'pdf' | 'text'>('text');
  const [pdf, setPdf] = useState<File | null>(null);
  const [sourceText, setSourceText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const quiz = await generateQuiz({
        title,
        pdf: mode === 'pdf' ? (pdf ?? undefined) : undefined,
        source_text: mode === 'text' ? sourceText : undefined,
      });
      navigate(`/quiz/${quiz.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Échec de la génération.'));
    } finally {
      setLoading(false);
    }
  };

  const handlePdfChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    if (file && file.size > MAX_PDF_SIZE) {
      // Trop volumineux : on refuse le fichier et on bloque l'upload.
      setError(
        'Le PDF dépasse la taille maximale autorisée (5 Mo). Choisissez un fichier plus léger.',
      );
      setPdf(null);
      // On vide l'input pour permettre de re-sélectionner le même fichier après correction.
      e.target.value = '';
      return;
    }
    // Fichier valide (ou aucun fichier) : on efface une éventuelle erreur de taille précédente.
    setError(null);
    setPdf(file);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-slate-900 mb-2">Créer un nouveau quiz</h1>
      <p className="text-slate-600 mb-6">
        Uploade un PDF ou colle un texte. EduTutor IA génère 10 questions QCM.
      </p>

      {error && (
        <div className="mb-4 p-3 bg-rose-50 border-l-4 border-rose-500 text-sm text-rose-900 rounded">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="card space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Titre du cours</label>
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex. Histoire — Révolution française"
            className="input"
          />
        </div>

        <div>
          <div className="flex gap-2 mb-3">
            <button
              type="button"
              onClick={() => setMode('text')}
              className={`px-3 py-1 rounded text-sm font-medium ${
                mode === 'text'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              📝 Texte collé
            </button>
            <button
              type="button"
              onClick={() => setMode('pdf')}
              className={`px-3 py-1 rounded text-sm font-medium ${
                mode === 'pdf'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              📄 PDF
            </button>
          </div>

          {mode === 'text' ? (
            <textarea
              required
              rows={10}
              minLength={200}
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Collez ici le texte de votre cours (au moins 200 caractères)…"
              className="input"
            />
          ) : (
            <input
              type="file"
              accept=".pdf,application/pdf"
              required
              onChange={handlePdfChange}
              className="input"
            />
          )}
          {mode === 'text' && (
            <p className="text-xs text-slate-500 mt-1">
              {sourceText.length} / 200 caractères minimum
            </p>
          )}
        </div>

        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading ? (
            <>
              <span className="animate-spin">⏳</span> Génération en cours… (1 à 5 min sur CPU,
              patientez)
            </>
          ) : (
            <>🚀 Générer le quiz</>
          )}
        </button>

        <p className="text-xs text-slate-500 text-center">
          La génération peut prendre de 1 à 5 minutes selon votre machine (bien plus rapide avec un
          GPU ou un modèle plus léger).
        </p>
      </form>
    </div>
  );
}
