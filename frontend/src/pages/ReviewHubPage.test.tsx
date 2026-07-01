import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReviewHubPage from './ReviewHubPage';
import { listQuizzes, type QuizSummary } from '@/api/quizzes';
import { listStudyDocs, type StudyDocSummary } from '@/api/llm';

// On isole la page : pas de vrai appel réseau vers les API quizzes / llm.
vi.mock('@/api/quizzes', () => ({
  listQuizzes: vi.fn(),
}));
vi.mock('@/api/llm', () => ({
  listStudyDocs: vi.fn(),
}));

const mockedListQuizzes = vi.mocked(listQuizzes);
const mockedListStudyDocs = vi.mocked(listStudyDocs);

const QUIZZES: QuizSummary[] = [
  {
    id: 1,
    title: 'Mon QCM Histoire',
    score: 8,
    nb_questions: 15,
    created_at: '2026-06-01T00:00:00Z',
  },
];

const DOCS: StudyDocSummary[] = [
  { id: 10, kind: 'note', title: 'Ma fiche Maths', created_at: '2026-06-02T00:00:00Z' },
  { id: 20, kind: 'summary', title: 'Mon résumé SVT', created_at: '2026-06-03T00:00:00Z' },
];

function renderHub() {
  return render(
    <MemoryRouter>
      <ReviewHubPage />
    </MemoryRouter>,
  );
}

describe('ReviewHubPage — menu déroulant QCM / Fiche / Résumé', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListQuizzes.mockResolvedValue({ count: 1, next: null, previous: null, results: QUIZZES });
    mockedListStudyDocs.mockResolvedValue(DOCS);
  });

  it('affiche les QCM par défaut, cliquables vers /quiz/:id', async () => {
    renderHub();
    const link = await screen.findByRole('link', { name: /Mon QCM Histoire/ });
    expect(link).toHaveAttribute('href', '/quiz/1');
    // Les fiches et résumés ne sont pas affichés dans la vue QCM.
    expect(screen.queryByText(/Ma fiche Maths/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Mon résumé SVT/)).not.toBeInTheDocument();
  });

  it('choix « Fiche de révision » → liste les notes, cliquables vers /study/:id', async () => {
    renderHub();
    await screen.findByRole('link', { name: /Mon QCM Histoire/ });

    fireEvent.change(screen.getByLabelText(/Que souhaitez-vous revoir/), {
      target: { value: 'note' },
    });

    const link = await screen.findByRole('link', { name: /Ma fiche Maths/ });
    expect(link).toHaveAttribute('href', '/study/10');
    expect(screen.queryByText(/Mon résumé SVT/)).not.toBeInTheDocument();
  });

  it('choix « Résumé » → liste les résumés, cliquables vers /study/:id', async () => {
    renderHub();
    await screen.findByRole('link', { name: /Mon QCM Histoire/ });

    fireEvent.change(screen.getByLabelText(/Que souhaitez-vous revoir/), {
      target: { value: 'summary' },
    });

    const link = await screen.findByRole('link', { name: /Mon résumé SVT/ });
    expect(link).toHaveAttribute('href', '/study/20');
    expect(screen.queryByText(/Ma fiche Maths/)).not.toBeInTheDocument();
  });

  it('charge chaque source une seule fois (le select ne fait que filtrer)', async () => {
    renderHub();
    await screen.findByRole('link', { name: /Mon QCM Histoire/ });

    fireEvent.change(screen.getByLabelText(/Que souhaitez-vous revoir/), {
      target: { value: 'note' },
    });
    fireEvent.change(screen.getByLabelText(/Que souhaitez-vous revoir/), {
      target: { value: 'summary' },
    });

    await waitFor(() => expect(mockedListStudyDocs).toHaveBeenCalledTimes(1));
    expect(mockedListQuizzes).toHaveBeenCalledTimes(1);
  });
});
