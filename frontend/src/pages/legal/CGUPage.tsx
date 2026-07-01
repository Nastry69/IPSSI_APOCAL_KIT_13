/** Conditions Générales d'Utilisation d'EduTutor IA. */
import LegalScaffold, { type LegalSection } from './LegalScaffold';

const SECTIONS: LegalSection[] = [
  {
    title: 'Objet',
    hint: 'ce que régissent ces CGU et le service concerné (EduTutor IA).',
    content: (
      <p>
        Les présentes CGU régissent l'utilisation du service EduTutor IA, une application
        pédagogique qui génère des quiz à choix multiples à partir du texte de cours fourni par
        l'utilisateur.
      </p>
    ),
  },
  {
    title: 'Acceptation des conditions',
    hint: "comment l'utilisateur accepte les CGU (inscription, usage…).",
    content: (
      <p>
        La création d'un compte vaut acceptation pleine et entière des présentes CGU et de la
        politique de confidentialité. L'utilisateur atteste avoir coché la case d'acceptation lors
        de son inscription ; la date et la version acceptées sont enregistrées.
      </p>
    ),
  },
  {
    title: 'Accès au service',
    hint: "conditions d'accès, disponibilité, prérequis techniques.",
    content: (
      <p>
        Le service est accessible en ligne via un navigateur récent. Il est fourni « en l'état »,
        dans un cadre pédagogique, sans garantie de disponibilité continue. Des interruptions
        peuvent survenir pour maintenance ou pour des raisons techniques.
      </p>
    ),
  },
  {
    title: 'Compte utilisateur',
    hint: 'création, responsabilité du mot de passe, exactitude des informations.',
    content: (
      <p>
        L'utilisateur s'engage à fournir une adresse email valide, à conserver son mot de passe
        confidentiel et à ne pas partager son compte. Il est responsable des actions réalisées
        depuis son compte. Toute perte de mot de passe peut être réinitialisée via la fonction « mot
        de passe oublié ».
      </p>
    ),
  },
  {
    title: 'Comportements interdits',
    hint: 'usages abusifs, contenus illicites, atteinte à la sécurité.',
    content: (
      <p>
        Sont notamment interdits : le téléversement de contenus illicites, diffamatoires ou portant
        atteinte aux droits de tiers ; toute tentative d'atteinte à la sécurité ou à l'intégrité du
        service ; l'usage automatisé abusif ; le dépôt de données personnelles de tiers ou de
        données sensibles dans le texte des cours.
      </p>
    ),
  },
  {
    title: 'Contenu généré par IA',
    hint: "limites des quiz générés (peuvent contenir des erreurs), responsabilité de l'utilisateur.",
    content: (
      <p>
        Les quiz sont générés automatiquement par un modèle d'intelligence artificielle. Ils{' '}
        <strong>peuvent contenir des erreurs ou des imprécisions</strong>. L'utilisateur reste
        responsable de la vérification des contenus générés avant tout usage pédagogique ou
        évaluatif. EduTutor IA ne garantit pas l'exactitude des quiz produits.
      </p>
    ),
  },
  {
    title: 'Responsabilité',
    hint: "limites de responsabilité de l'éditeur.",
    content: (
      <p>
        L'éditeur ne saurait être tenu responsable des dommages indirects liés à l'utilisation du
        service, ni des conséquences d'une utilisation de contenus générés par l'IA sans
        vérification. Le service étant pédagogique, il est fourni sans garantie de résultat.
      </p>
    ),
  },
  {
    title: 'Propriété intellectuelle',
    hint: "droits sur le service et sur les contenus déposés par l'utilisateur.",
    content: (
      <p>
        Le service et ses composants appartiennent à l'Équipe 13 / EduTutor IA (voir Mentions
        légales). Les contenus déposés par l'utilisateur (texte des cours) restent sa propriété ;
        l'utilisateur garantit détenir les droits nécessaires sur les textes qu'il téléverse.
      </p>
    ),
  },
  {
    title: 'Modification des CGU',
    hint: 'comment et quand les CGU peuvent évoluer.',
    content: (
      <p>
        Les présentes CGU peuvent évoluer. En cas de modification substantielle, une nouvelle
        version (identifiée par sa date) sera publiée et pourra faire l'objet d'une nouvelle
        acceptation. La version en vigueur est celle affichée sur cette page.
      </p>
    ),
  },
  {
    title: 'Droit applicable et litiges',
    hint: 'droit applicable et juridiction compétente.',
    content: (
      <p>
        Les présentes CGU sont soumises au <strong>droit français</strong>. À défaut de résolution
        amiable, tout litige relève de la compétence des <strong>tribunaux français</strong>.
      </p>
    ),
  },
];

export default function CGUPage() {
  return (
    <LegalScaffold
      title="Conditions Générales d'Utilisation"
      intro="Les règles d'utilisation du service EduTutor IA, acceptées par chaque utilisateur."
      sections={SECTIONS}
      updatedAt="1er juillet 2026"
    />
  );
}
