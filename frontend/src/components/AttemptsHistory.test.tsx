import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AttemptsHistory from './AttemptsHistory';
import { getAttempts, type Attempt, type QuizSummary } from '@/api/quizzes';

// On isole le composant : pas de vrai appel réseau.
vi.mock('@/api/quizzes', () => ({
  getAttempts: vi.fn(),
}));

const mockedGetAttempts = vi.mocked(getAttempts);

const quizzes: QuizSummary[] = [
  { id: 1, title: 'Histoire', score: 8, nb_questions: 10, created_at: '2026-06-01T10:00:00Z' },
  { id: 2, title: 'Maths', score: 5, nb_questions: 10, created_at: '2026-06-02T10:00:00Z' },
];

const attemptsQuiz1: Attempt[] = [
  { id: 20, number: 2, score: 8, total: 10, created_at: '2026-06-10T10:00:00Z' },
  { id: 10, number: 1, score: 6, total: 10, created_at: '2026-06-05T10:00:00Z' },
];

function renderHistory() {
  return render(
    <MemoryRouter>
      <AttemptsHistory quizzes={quizzes} />
    </MemoryRouter>,
  );
}

describe('AttemptsHistory — barres + onglets des tentatives', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('charge les tentatives du premier quiz et affiche une barre par tentative', async () => {
    mockedGetAttempts.mockResolvedValueOnce(attemptsQuiz1);

    renderHistory();

    // Le composant charge les tentatives du quiz actif (le premier) au montage.
    await waitFor(() => expect(mockedGetAttempts).toHaveBeenCalledWith(1));

    // Une barre par tentative : chaque tentative pointe vers sa page de détail.
    const links = await screen.findAllByRole('link', { name: /Tentative #/i });
    expect(links).toHaveLength(attemptsQuiz1.length);

    // Le lien de détail cible bien la route /quiz/:id/attempts/:attemptId.
    expect(links.map((l) => l.getAttribute('href'))).toEqual(
      expect.arrayContaining(['/quiz/1/attempts/10', '/quiz/1/attempts/20']),
    );
  });

  it('recharge les tentatives du quiz sélectionné au changement d’onglet', async () => {
    mockedGetAttempts.mockResolvedValue([]);

    renderHistory();
    await waitFor(() => expect(mockedGetAttempts).toHaveBeenCalledWith(1));

    // On bascule sur l'onglet du second quiz.
    fireEvent.click(screen.getByRole('button', { name: 'Maths' }));

    await waitFor(() => expect(mockedGetAttempts).toHaveBeenCalledWith(2));
  });

  it('affiche un état vide quand aucun quiz n’a été passé', () => {
    render(
      <MemoryRouter>
        <AttemptsHistory quizzes={[]} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Aucune tentative pour l'instant/i)).toBeInTheDocument();
    // Aucun quiz -> aucun appel réseau.
    expect(mockedGetAttempts).not.toHaveBeenCalled();
  });
});
