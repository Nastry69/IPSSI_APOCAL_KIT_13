import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import QuizPage from './QuizPage';
import { getQuiz, submitAnswers, type Quiz, type AnswerResult } from '@/api/quizzes';

// On isole la page : pas de vrai appel réseau vers l'API quizzes.
vi.mock('@/api/quizzes', () => ({
  getQuiz: vi.fn(),
  submitAnswers: vi.fn(),
}));

const mockedGetQuiz = vi.mocked(getQuiz);
const mockedSubmitAnswers = vi.mocked(submitAnswers);

/** Construit un quiz factice avec `n` questions (4 options chacune). */
function makeQuiz(n: number): Quiz {
  return {
    id: 1,
    title: 'Quiz de test',
    source_text: '',
    score: null,
    created_at: '2026-07-01T00:00:00Z',
    questions: Array.from({ length: n }, (_, i) => ({
      index: i + 1,
      prompt: `Question ${i + 1} ?`,
      options: ['A', 'B', 'C', 'D'],
      correct_index: 0,
    })),
  };
}

function renderQuiz() {
  return render(
    <MemoryRouter initialEntries={['/quiz/1']}>
      <Routes>
        <Route path="/quiz/:id" element={<QuizPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Sélectionne l'option A pour chacune des `n` premières questions affichées. */
function answerAll(n: number) {
  // Les boutons d'option commencent par « A. », « B. »… : on prend tous les « A. ».
  const optionButtons = screen.getAllByRole('button', { name: /^A\./ });
  for (let i = 0; i < n; i++) {
    fireEvent.click(optionButtons[i]!);
  }
}

describe('QuizPage — soumission basée sur le nombre RÉEL de questions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('un quiz de 15 questions peut être soumis quand toutes sont répondues', async () => {
    mockedGetQuiz.mockResolvedValueOnce(makeQuiz(15));
    const result: AnswerResult = {
      score: 12,
      total: 15,
      details: [],
      attempt_id: 99,
      number: 1,
    };
    mockedSubmitAnswers.mockResolvedValueOnce(result);

    renderQuiz();
    await screen.findByText(/Quiz de test/);

    // Le libellé reflète le total réel (15), pas 10.
    expect(screen.getByText(/Répondre à toutes les questions \(0\/15\)/)).toBeInTheDocument();

    answerAll(15);

    const submit = screen.getByRole('button', { name: /Soumettre mes réponses/ });
    expect(submit).not.toBeDisabled();
    fireEvent.click(submit);

    await waitFor(() => expect(mockedSubmitAnswers).toHaveBeenCalledTimes(1));
    // Le payload contient bien 15 réponses.
    expect(mockedSubmitAnswers.mock.calls[0]![1]).toHaveLength(15);

    // Le score s'affiche sur le total réel renvoyé par l'API.
    await screen.findByText('Score : 12 / 15');
  });

  it('le bouton reste désactivé tant que les 15 questions ne sont pas toutes répondues', async () => {
    mockedGetQuiz.mockResolvedValueOnce(makeQuiz(15));

    renderQuiz();
    await screen.findByText(/Quiz de test/);

    // On ne répond qu'à 10 questions (l'ancien seuil codé en dur).
    answerAll(10);

    expect(screen.getByText(/Répondre à toutes les questions \(10\/15\)/)).toBeInTheDocument();
    const submit = screen.getByRole('button', { name: /Répondre à toutes les questions/ });
    expect(submit).toBeDisabled();
    expect(mockedSubmitAnswers).not.toHaveBeenCalled();
  });
});
