/**
 * Modale « Exporter mes données » (RGPD, droit à la portabilité).
 *
 * Propose 4 formats en téléchargement DIRECT : CSV, JSON, HTML, XLSX (Excel).
 * Chaque bouton appelle `downloadDataExport(format)` (client axios + token) et
 * déclenche le téléchargement du fichier côté navigateur.
 *
 * Simple par conception (props : open / onClose, aucune dépendance externe) :
 *   - overlay semi-transparent cliquable pour fermer,
 *   - bouton « Fermer » explicite,
 *   - touche Échap pour fermer,
 *   - état de chargement + gestion d'erreur via getApiErrorMessage.
 */
import { useEffect, useState } from 'react';
import { downloadDataExport, type ExportFormat } from '@/api/auth';
import { getApiErrorMessage } from '@/api/errors';

type ExportModalProps = {
  /** La modale est-elle visible ? */
  open: boolean;
  /** Callback de fermeture (overlay, bouton, Échap). */
  onClose: () => void;
};

/** Formats proposés, avec libellé lisible. */
const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: 'csv', label: 'CSV' },
  { format: 'json', label: 'JSON' },
  { format: 'html', label: 'HTML' },
  { format: 'xlsx', label: 'Excel (XLSX)' },
];

export default function ExportModal({ open, onClose }: ExportModalProps) {
  // Format en cours de téléchargement (null = aucun) → sert d'état de chargement.
  const [loading, setLoading] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fermeture au clavier (Échap) tant que la modale est ouverte.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  // Réinitialise l'erreur à chaque ouverture (repart propre).
  useEffect(() => {
    if (open) setError(null);
  }, [open]);

  if (!open) return null;

  const handleDownload = async (format: ExportFormat) => {
    setError(null);
    setLoading(format);
    try {
      await downloadDataExport(format);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Export impossible.'));
    } finally {
      setLoading(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="card w-full max-w-md"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-2">
          <h2 id="export-modal-title" className="text-lg font-semibold text-slate-900">
            Exporter mes données
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="text-slate-400 hover:text-slate-600 text-xl leading-none"
          >
            ×
          </button>
        </div>
        <p className="text-sm text-slate-500 mb-4">
          Téléchargez une copie de toutes vos données (compte, profil, quiz) dans le format de votre
          choix.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border-l-4 border-rose-500 text-sm text-rose-900 rounded">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          {FORMATS.map(({ format, label }) => (
            <button
              key={format}
              type="button"
              onClick={() => handleDownload(format)}
              disabled={loading !== null}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading === format ? 'Téléchargement…' : label}
            </button>
          ))}
        </div>

        <div className="mt-4 flex justify-end">
          <button type="button" onClick={onClose} className="btn-secondary">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}
