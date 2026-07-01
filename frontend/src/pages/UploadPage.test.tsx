import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import UploadPage from './UploadPage';
import { generateQuiz } from '@/api/llm';

// On isole la page : pas de vrai appel réseau vers l'API LLM.
vi.mock('@/api/llm', () => ({
  generateQuiz: vi.fn(),
}));

const mockedGenerateQuiz = vi.mocked(generateQuiz);

/**
 * Fabrique un faux PDF de taille arbitraire sans allouer réellement la mémoire.
 * `new File` calcule la taille depuis le contenu ; on écrase donc la propriété
 * `size` pour simuler un fichier volumineux (ou léger) de façon déterministe.
 */
function makePdf(name: string, size: number): File {
  const file = new File(['%PDF-1.4'], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

function renderUpload() {
  return render(
    <MemoryRouter>
      <UploadPage />
    </MemoryRouter>,
  );
}

/** Passe la page en mode PDF et renvoie l'input fichier (non labellisé). */
function switchToPdfMode(container: HTMLElement): HTMLInputElement {
  fireEvent.click(screen.getByRole('button', { name: /pdf/i }));
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input).not.toBeNull();
  return input;
}

const MB = 1024 * 1024;

describe('UploadPage — garde-fou taille PDF (5 Mo)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('refuse un PDF > 5 Mo : affiche un message d’erreur et n’accepte pas le fichier', () => {
    const { container } = renderUpload();
    const input = switchToPdfMode(container);

    // 6 Mo : au-dessus de la limite de 5 Mo.
    const tooBig = makePdf('gros.pdf', 6 * MB);
    fireEvent.change(input, { target: { files: [tooBig] } });

    // Un message d'erreur clair mentionnant la limite de 5 Mo apparaît.
    expect(screen.getByText(/5\s*Mo/i)).toBeInTheDocument();

    // Le fichier n'est pas accepté : le garde-fou vide la valeur de l'input.
    // (En navigateur réel, value='' réinitialise aussi .files ; jsdom ne reflète
    //  pas cette réinitialisation — on ne vérifie donc que .value ici.)
    expect(input.value).toBe('');

    // La sélection elle-même ne déclenche aucun appel d'upload.
    expect(mockedGenerateQuiz).not.toHaveBeenCalled();
  });

  it('accepte un PDF <= 5 Mo : aucun message d’erreur de taille', () => {
    const { container } = renderUpload();
    const input = switchToPdfMode(container);

    // 4 Mo : sous la limite.
    const ok = makePdf('petit.pdf', 4 * MB);
    fireEvent.change(input, { target: { files: [ok] } });

    // Pas de message d'erreur de taille affiché.
    expect(screen.queryByText(/5\s*Mo/i)).not.toBeInTheDocument();

    // Le fichier est bien retenu par l'input (comportement inchangé).
    expect(input.files?.[0]).toBe(ok);
  });

  it('accepte un PDF pile à la limite de 5 Mo (cas limite inclusif)', () => {
    const { container } = renderUpload();
    const input = switchToPdfMode(container);

    // Exactement 5 Mo : la limite est `> MAX`, donc 5 Mo pile passe.
    const atLimit = makePdf('limite.pdf', 5 * MB);
    fireEvent.change(input, { target: { files: [atLimit] } });

    expect(screen.queryByText(/5\s*Mo/i)).not.toBeInTheDocument();
    expect(input.files?.[0]).toBe(atLimit);
  });

  it('efface l’erreur de taille lorsqu’on re-sélectionne ensuite un PDF valide', () => {
    const { container } = renderUpload();
    const input = switchToPdfMode(container);

    // 1) Fichier trop gros -> erreur.
    fireEvent.change(input, { target: { files: [makePdf('gros.pdf', 6 * MB)] } });
    expect(screen.getByText(/5\s*Mo/i)).toBeInTheDocument();

    // 2) Fichier valide -> l'erreur disparaît.
    const ok = makePdf('petit.pdf', 2 * MB);
    fireEvent.change(input, { target: { files: [ok] } });
    expect(screen.queryByText(/5\s*Mo/i)).not.toBeInTheDocument();
    expect(input.files?.[0]).toBe(ok);
  });

  it('lance l’upload avec le PDF quand il est valide et le formulaire soumis', async () => {
    mockedGenerateQuiz.mockResolvedValueOnce({
      id: 42,
      title: 'Mon cours',
      source_text: '',
      score: null,
      created_at: '2026-07-01T00:00:00Z',
      questions: [],
    });

    const { container } = renderUpload();

    // Titre requis. Le label n'étant pas associé à l'input, on cible via le placeholder.
    fireEvent.change(screen.getByPlaceholderText(/Histoire/i), {
      target: { value: 'Mon cours' },
    });

    const input = switchToPdfMode(container);
    const ok = makePdf('petit.pdf', 3 * MB);
    fireEvent.change(input, { target: { files: [ok] } });

    fireEvent.submit(input.closest('form') as HTMLFormElement);

    await waitFor(() => expect(mockedGenerateQuiz).toHaveBeenCalledTimes(1));
    expect(mockedGenerateQuiz).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Mon cours', pdf: ok }),
    );
  });
});
