import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TeacherPage from './TeacherPage';
import { getClasses, getClassProgress } from '@/api/classes';
import type { User } from '@/api/auth';

// On isole la page : pas de vrai appel réseau vers l'API classes.
vi.mock('@/api/classes', () => ({
  getClasses: vi.fn(),
  getClassProgress: vi.fn(),
  getStudentAttempt: vi.fn(),
  // Les helpers de libellé restent des fonctions pures réutilisées dans la page.
  classLabel: (c: { name?: string; title?: string; code: string }) => c.name || c.title || c.code,
  studentLabel: (s: { first_name?: string; last_name?: string; username: string }) =>
    `${s.first_name ?? ''} ${s.last_name ?? ''}`.trim() || s.username,
}));

// Le rôle de l'utilisateur pilote le gating de la page. On le rend mutable.
let mockUser: User | null = null;
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}));

const mockedGetClasses = vi.mocked(getClasses);
const mockedGetClassProgress = vi.mocked(getClassProgress);

const teacher: User = {
  id: 1,
  username: 'prof@test.com',
  email: 'prof@test.com',
  role: 'teacher',
};

const classes = [{ id: 10, name: 'Terminale B', code: 'ABC234', student_count: 2 }];

const progress = [
  {
    student: { id: 100, first_name: 'Alice', last_name: 'Martin', username: 'alice' },
    quizzes_taken: 3,
    average_score: 7,
    best_score: 9,
    last_score: 8,
    evolution: [
      {
        attempt_id: 500,
        quiz_id: 1,
        quiz_title: 'Histoire',
        number: 1,
        score: 6,
        total: 10,
        created_at: '2026-06-01T10:00:00Z',
      },
    ],
  },
  {
    student: { id: 101, first_name: 'Bob', last_name: 'Durand', username: 'bob' },
    quizzes_taken: 1,
    average_score: 4,
    best_score: 4,
    last_score: 4,
    evolution: [],
  },
];

function renderTeacher() {
  return render(
    <MemoryRouter>
      <TeacherPage />
    </MemoryRouter>,
  );
}

describe('TeacherPage — espace prof', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = teacher;
  });

  it('gate : un non-enseignant voit un message « réservé aux enseignants »', () => {
    mockUser = { ...teacher, role: 'student' };
    renderTeacher();

    expect(screen.getByText(/réservé aux enseignants/i)).toBeInTheDocument();
    // Aucune classe n'est chargée pour un élève.
    expect(mockedGetClasses).not.toHaveBeenCalled();
  });

  it('charge les classes puis la progression de la classe active', async () => {
    mockedGetClasses.mockResolvedValueOnce(classes);
    mockedGetClassProgress.mockResolvedValueOnce(progress);

    renderTeacher();

    // getClasses est appelé au montage (utilisateur enseignant).
    await waitFor(() => expect(mockedGetClasses).toHaveBeenCalledTimes(1));
    // La progression de la première classe est chargée automatiquement.
    await waitFor(() => expect(mockedGetClassProgress).toHaveBeenCalledWith(10));

    // Les deux élèves apparaissent.
    expect(await screen.findByText('Alice Martin')).toBeInTheDocument();
    expect(screen.getByText('Bob Durand')).toBeInTheDocument();
  });

  it('le filtre de recherche restreint la liste des élèves par nom', async () => {
    mockedGetClasses.mockResolvedValueOnce(classes);
    mockedGetClassProgress.mockResolvedValueOnce(progress);

    renderTeacher();
    expect(await screen.findByText('Alice Martin')).toBeInTheDocument();
    expect(screen.getByText('Bob Durand')).toBeInTheDocument();

    // On tape « bob » : seul Bob doit rester affiché.
    fireEvent.change(screen.getByPlaceholderText(/Rechercher un élève/i), {
      target: { value: 'bob' },
    });

    expect(screen.getByText('Bob Durand')).toBeInTheDocument();
    expect(screen.queryByText('Alice Martin')).not.toBeInTheDocument();
  });
});
