import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LegalScaffold, { type LegalSection } from './LegalScaffold';

describe('LegalScaffold', () => {
  it('affiche le contenu réel quand une rubrique a un `content`', () => {
    const sections: LegalSection[] = [
      {
        title: 'Responsable du traitement',
        hint: 'qui décide pourquoi et comment les données sont traitées.',
        content: <p>L'Équipe 13 du projet EduTutor IA est responsable du traitement.</p>,
      },
    ];

    render(<LegalScaffold title="Politique" intro="Intro" sections={sections} />);

    // Le contenu réel est rendu…
    expect(
      screen.getByText(/L'Équipe 13 du projet EduTutor IA est responsable du traitement\./),
    ).toBeInTheDocument();
    // …et le placeholder « À compléter » n'apparaît pas.
    expect(screen.queryByText(/À compléter/)).not.toBeInTheDocument();
  });

  it("affiche « À compléter — {hint} » quand une rubrique n'a pas de `content`", () => {
    const sections: LegalSection[] = [
      {
        title: 'Durée de conservation',
        hint: 'combien de temps les données sont gardées.',
      },
    ];

    render(<LegalScaffold title="Politique" intro="Intro" sections={sections} />);

    expect(
      screen.getByText('À compléter — combien de temps les données sont gardées.'),
    ).toBeInTheDocument();
  });

  it('masque le bandeau « Page à compléter » quand toutes les rubriques ont un `content`', () => {
    const sections: LegalSection[] = [
      { title: 'A', hint: 'hint A', content: <p>Contenu A</p> },
      { title: 'B', hint: 'hint B', content: <p>Contenu B</p> },
    ];

    render(<LegalScaffold title="Politique" intro="Intro" sections={sections} />);

    expect(screen.queryByText(/Page à compléter par votre équipe/)).not.toBeInTheDocument();
  });

  it("affiche le bandeau « Page à compléter » dès qu'une rubrique n'a pas de `content`", () => {
    const sections: LegalSection[] = [
      { title: 'A', hint: 'hint A', content: <p>Contenu A</p> },
      { title: 'B', hint: 'hint B' },
    ];

    render(<LegalScaffold title="Politique" intro="Intro" sections={sections} />);

    expect(screen.getByText(/Page à compléter par votre équipe/)).toBeInTheDocument();
  });

  it('affiche la date de dernière mise à jour fournie', () => {
    render(
      <LegalScaffold
        title="Politique"
        intro="Intro"
        sections={[{ title: 'A', hint: 'hint A', content: <p>Contenu A</p> }]}
        updatedAt="1er juillet 2026"
      />,
    );

    expect(screen.getByText('1er juillet 2026')).toBeInTheDocument();
  });
});
