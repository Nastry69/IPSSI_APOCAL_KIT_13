/** Mentions légales d'EduTutor IA. */
import LegalScaffold, { type LegalSection } from './LegalScaffold';

const SECTIONS: LegalSection[] = [
  {
    title: 'Éditeur du site',
    hint: "nom de l'organisation/équipe, statut, adresse, email de contact.",
    content: (
      <>
        <p>
          Le site EduTutor IA (
          <a
            href="https://apocalipssi26.elafrit.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:underline"
          >
            https://apocalipssi26.elafrit.com
          </a>
          ) est édité par l'<strong>Équipe 13</strong> dans le cadre du projet pédagogique
          APOCAL'IPSSI 2026 à l'IPSSI. Statut : projet étudiant à but non lucratif et pédagogique.
        </p>
        <p>
          Membres de l'équipe : Tristan DZIOCH, Sebastien GERARD, Syphax ALILI, Killian MARTINS,
          Amine TALEB, Jacqueline MAPENZI et Moussa DIOP.
        </p>
        <p>Adresse : 10 rue de l'Exemple, 75000 Paris. Email : contact@edututor-ipssi.fr.</p>
      </>
    ),
  },
  {
    title: 'Directeur de la publication',
    hint: 'nom de la personne responsable du contenu publié.',
    content: (
      <p>
        Le directeur de la publication est l'Équipe 13 du projet EduTutor IA, représentée par son
        référent : Sébastien GERARD.
      </p>
    ),
  },
  {
    title: 'Hébergeur',
    hint: "nom, adresse et téléphone de l'hébergeur du site.",
    content: (
      <p>
        Le site est hébergé sur un serveur privé virtuel (VPS) OVHcloud. Hébergeur :{' '}
        <strong>OVH SAS</strong>, 2 rue Kellermann, 59100 Roubaix, France. Téléphone : 1007. Site :{' '}
        <a
          href="https://www.ovhcloud.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-600 hover:underline"
        >
          www.ovhcloud.com
        </a>
        .
      </p>
    ),
  },
  {
    title: 'Propriété intellectuelle',
    hint: 'à qui appartiennent les textes, logos, code, contenus.',
    content: (
      <p>
        Le code source, la charte graphique, les textes et l'ensemble des éléments du site (hors
        contenus déposés par les utilisateurs) sont la propriété de l'Équipe 13 / du projet EduTutor
        IA, ou sont utilisés sous licence (voir le fichier LICENSE du dépôt). Les contenus que vous
        déposez (texte de vos cours) restent votre propriété ; vous nous accordez le droit de les
        traiter pour la seule fourniture du service. Toute reproduction non autorisée est interdite.
      </p>
    ),
  },
  {
    title: 'Contact',
    hint: 'comment vous joindre pour toute question juridique.',
    content: <p>Pour toute question juridique ou relative au site : legal@edututor-ipssi.fr.</p>,
  },
];

export default function MentionsLegalesPage() {
  return (
    <LegalScaffold
      title="Mentions légales"
      intro="Informations légales obligatoires identifiant l'éditeur et l'hébergeur du site."
      sections={SECTIONS}
      updatedAt="1er juillet 2026"
    />
  );
}
