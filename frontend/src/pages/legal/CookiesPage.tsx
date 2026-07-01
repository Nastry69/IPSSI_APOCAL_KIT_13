/** Politique de gestion des cookies d'EduTutor IA. */
import LegalScaffold, { type LegalSection } from './LegalScaffold';

const SECTIONS: LegalSection[] = [
  {
    title: "Qu'est-ce qu'un cookie ?",
    hint: 'définition simple à destination des utilisateurs.',
    content: (
      <p>
        Un cookie est un petit fichier déposé par un site sur votre appareil. Plus largement, un
        site peut aussi utiliser d'autres formes de stockage local du navigateur (comme le{' '}
        <code className="bg-slate-100 px-1 rounded">localStorage</code>) pour mémoriser des
        informations techniques nécessaires à son fonctionnement.
      </p>
    ),
  },
  {
    title: 'Cookies et stockage utilisés',
    hint: "lister ce que le site dépose (ex. token d'authentification en localStorage).",
    content: (
      <>
        <p>
          EduTutor IA utilise uniquement des dispositifs <strong>techniques</strong> :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            un <strong>cookie de session</strong> applicatif (
            <code className="bg-slate-100 px-1 rounded">sessionid</code>), posé par le serveur lors
            de la connexion, utile notamment à l'interface d'administration/documentation ;
          </li>
          <li>
            un <strong>token d'authentification</strong> stocké dans le{' '}
            <code className="bg-slate-100 px-1 rounded">localStorage</code> de votre navigateur, qui
            vous maintient connecté entre deux visites.
          </li>
        </ul>
        <p>Aucun cookie tiers, publicitaire ou de mesure d'audience n'est déposé.</p>
      </>
    ),
  },
  {
    title: 'Finalité de chaque cookie',
    hint: "à quoi sert chaque cookie/stockage (technique, mesure d'audience…).",
    content: (
      <p>
        Le cookie de session et le token d'authentification servent exclusivement à vous{' '}
        <strong>identifier et vous maintenir connecté</strong> en toute sécurité. Ils sont{' '}
        <strong>strictement nécessaires</strong> au fonctionnement du service.
      </p>
    ),
  },
  {
    title: 'Consentement',
    hint: 'cookies nécessitant un consentement préalable et comment il est recueilli.',
    content: (
      <p>
        Les cookies et stockages strictement nécessaires au fonctionnement d'un service sont{' '}
        <strong>exemptés de consentement</strong> (art. 82 loi Informatique et Libertés / lignes
        directrices CNIL). EduTutor IA n'utilisant <strong>que</strong> de tels dispositifs
        techniques, <strong>aucune bannière de consentement n'est requise</strong> et aucun traceur
        n'est activé sans votre action.
      </p>
    ),
  },
  {
    title: 'Durée de conservation',
    hint: 'combien de temps chaque cookie est conservé.',
    content: (
      <p>
        Le cookie de session expire à la fermeture de la session ou selon la configuration du
        serveur. Le token d'authentification reste dans le{' '}
        <code className="bg-slate-100 px-1 rounded">localStorage</code>{' '}
        <strong>jusqu'à votre déconnexion</strong> (bouton « Se déconnecter »), un changement de mot
        de passe, ou la suppression manuelle du stockage de votre navigateur.
      </p>
    ),
  },
  {
    title: 'Gérer ou refuser les cookies',
    hint: 'comment paramétrer ou supprimer les cookies (navigateur, bannière).',
    content: (
      <p>
        Vous pouvez à tout moment supprimer ces données via les réglages de votre navigateur
        (effacement des cookies et du stockage local) ou en vous déconnectant. Le refus ou la
        suppression du token d'authentification vous <strong>déconnectera</strong> simplement du
        service ; aucune autre fonctionnalité n'est affectée puisque aucun traceur non essentiel
        n'est utilisé.
      </p>
    ),
  },
];

export default function CookiesPage() {
  return (
    <LegalScaffold
      title="Politique de gestion des cookies"
      intro="Les cookies et technologies de stockage utilisés par le site, et comment les gérer."
      sections={SECTIONS}
      updatedAt="1er juillet 2026"
    >
      <div className="mt-6 p-3 bg-slate-50 border border-slate-200 rounded text-sm text-slate-600">
        💡 Indice pour votre équipe : ce kit stocke actuellement le{' '}
        <code className="bg-slate-200 px-1 rounded">token</code> d'authentification dans le{' '}
        <code className="bg-slate-200 px-1 rounded">localStorage</code> du navigateur. C'est un bon
        point de départ à documenter ici.
      </div>
    </LegalScaffold>
  );
}
