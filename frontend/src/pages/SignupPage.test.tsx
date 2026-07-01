import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SignupPage from './SignupPage';

// On isole la page : ni vrai appel API, ni vrais contextes.
vi.mock('@/api/auth', () => ({
  signup: vi.fn(),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ refresh: vi.fn() }),
}));

vi.mock('@/contexts/SiteConfigContext', () => ({
  useSiteConfig: () => ({ config: { allow_signups: true } }),
}));

function renderSignup() {
  return render(
    <MemoryRouter>
      <SignupPage />
    </MemoryRouter>,
  );
}

describe('SignupPage — consentement obligatoire', () => {
  it('désactive le bouton de soumission tant que la case n’est pas cochée', () => {
    renderSignup();

    const submit = screen.getByRole('button', { name: /créer mon compte/i });
    // Case décochée au chargement -> bouton désactivé.
    expect(submit).toBeDisabled();

    // On coche la case d'acceptation des CGU / politique de confidentialité.
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    // Une fois la case cochée, le bouton devient actif.
    expect(submit).toBeEnabled();
  });
});
