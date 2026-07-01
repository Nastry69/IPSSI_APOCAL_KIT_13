/** Politique de confidentialité d'EduTutor IA (RGPD). */
import { Link } from 'react-router-dom';
import LegalScaffold, { type LegalSection } from './LegalScaffold';

const SECTIONS: LegalSection[] = [
  {
    title: 'Responsable du traitement',
    hint: 'qui décide pourquoi et comment les données sont traitées.',
    content: (
      <>
        <p>
          Le responsable du traitement est l'<strong>Équipe 13</strong> du projet{' '}
          <strong>EduTutor IA</strong>, réalisé dans le cadre pédagogique APOCAL'IPSSI 2026 à
          l'IPSSI. Il s'agit d'un projet étudiant à but non lucratif, sans entité commerciale.
        </p>
        <p>
          L'équipe est composée de Tristan DZIOCH, Sebastien GERARD, Syphax ALILI, Killian MARTINS,
          Amine TALEB, Jacqueline MAPENZI et Moussa DIOP.
        </p>
        <p>Contact : dpo@edututor-ipssi.fr. Adresse postale : 10 rue de l'Exemple, 75000 Paris.</p>
      </>
    ),
  },
  {
    title: 'Données personnelles collectées',
    hint: 'email, nom, prénom, documents envoyés, historique de quiz…',
    content: (
      <>
        <p>Nous collectons uniquement les données nécessaires au fonctionnement du service :</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>Données de compte</strong> : adresse email (identifiant de connexion), nom et
            prénom (facultatifs).
          </li>
          <li>
            <strong>Données de contenu</strong> : le texte des cours que vous téléversez ou collez (
            <code className="bg-slate-100 px-1 rounded">source_text</code>), utilisé pour générer
            les quiz.
          </li>
          <li>
            <strong>Données d'usage pédagogique</strong> : quiz générés (titre, questions, options,
            bonne réponse) et historique de réponses (réponse sélectionnée, score obtenu).
          </li>
          <li>
            <strong>Données techniques</strong> : indicateur de vérification de l'email, dates de
            création du compte et des quiz, date et version du consentement.
          </li>
        </ul>
        <p>
          Nous ne collectons <strong>pas</strong> de données sensibles au sens de l'article 9 du
          RGPD, et nous vous demandons de ne pas insérer de telles données dans le texte des cours.
        </p>
      </>
    ),
  },
  {
    title: 'Finalités du traitement',
    hint: 'pourquoi vous collectez ces données (créer un compte, générer des quiz…).',
    content: (
      <>
        <p>Vos données sont traitées pour :</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>créer et gérer votre compte et vous authentifier ;</li>
          <li>générer des quiz à partir du texte de vos cours ;</li>
          <li>conserver votre historique de quiz et vos scores pour votre suivi pédagogique ;</li>
          <li>
            vous envoyer les emails de service (confirmation d'adresse, réinitialisation de mot de
            passe, export de vos données) ;
          </li>
          <li>assurer la sécurité et le bon fonctionnement du service.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Base légale',
    hint: 'consentement, contrat, intérêt légitime… (RGPD art. 6).',
    content: (
      <>
        <p>Conformément à l'article 6 du RGPD, les traitements reposent sur :</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>Exécution du contrat</strong> (art. 6-1-b) : gestion du compte et fourniture du
            service (génération de quiz, historique), fondée sur l'acceptation des CGU à
            l'inscription. L'envoi du texte des cours à un fournisseur LLM pour générer les quiz
            relève de cette même base (fonctionnalité cœur demandée par l'utilisateur).
          </li>
          <li>
            <strong>Intérêt légitime</strong> (art. 6-1-f) : emails de sécurité et bon
            fonctionnement du service.
          </li>
          <li>
            <strong>Consentement et obligation de responsabilité</strong> (art. 6-1-a,
            accountability) : conservation de la preuve du consentement aux CGU et à la politique de
            confidentialité, recueilli à l'inscription.
          </li>
        </ul>
      </>
    ),
  },
  {
    title: 'Durée de conservation',
    hint: 'combien de temps les données sont gardées, puis supprimées/anonymisées.',
    content: (
      <>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>Données de compte et de profil</strong> : conservées tant que le compte existe,
            puis supprimées immédiatement et définitivement lors de la suppression du compte
            (suppression en cascade des quiz et questions).
          </li>
          <li>
            <strong>Quiz, questions, historique et scores</strong> : même durée que le compte,
            supprimés avec lui.
          </li>
          <li>
            <strong>Preuve de consentement</strong> (date + version) : conservée pendant la durée de
            vie du compte.
          </li>
          <li>
            <strong>Exports de données</strong> : aucun export n'est stocké ; les fichiers sont
            générés à la demande et ne sont pas conservés côté serveur.
          </li>
        </ul>
        <p>
          Le service n'applique pas de suppression automatique pour inactivité à ce stade : les
          données sont conservées tant que le compte existe. L'utilisateur peut supprimer son compte
          à tout moment depuis son profil, ce qui efface immédiatement l'ensemble de ses données.
        </p>
      </>
    ),
  },
  {
    title: 'Destinataires des données',
    hint: 'qui y a accès (équipe, sous-traitants, fournisseurs LLM…).',
    content: (
      <>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            L'<strong>équipe pédagogique</strong> en charge d'EduTutor IA (administration
            technique).
          </li>
          <li>
            L'<strong>hébergeur</strong> OVHcloud (sous-traitant technique, hébergement du serveur
            et de la base).
          </li>
          <li>
            Le <strong>fournisseur d'emails</strong> Brevo (Sendinblue SAS) en production, pour
            l'acheminement des emails de service.
          </li>
          <li>
            Le <strong>fournisseur LLM</strong> configuré pour générer les quiz : selon la
            configuration du serveur, il peut s'agir de Mistral AI (UE) ou de fournisseurs hors UE
            (voir rubrique 7). Le texte de vos cours (
            <code className="bg-slate-100 px-1 rounded">source_text</code>) est transmis à ce
            fournisseur pour la seule finalité de génération des quiz.
          </li>
        </ul>
        <p>
          Vos données ne sont <strong>ni vendues, ni louées, ni cédées</strong> à des fins
          publicitaires.
        </p>
      </>
    ),
  },
  {
    title: 'Transferts hors UE',
    hint: 'si un fournisseur cloud héberge les données hors Union européenne.',
    content: (
      <>
        <p>
          Selon le fournisseur LLM activé, le texte de vos cours peut être transmis à des
          prestataires situés <strong>hors de l'Union européenne</strong> : <strong>OpenAI</strong>,{' '}
          <strong>Groq</strong>, <strong>Cerebras</strong> (États-Unis),{' '}
          <strong>Google Gemini</strong> (Google, États-Unis), <strong>Anthropic</strong> (Claude,
          États-Unis) et <strong>OpenRouter</strong> (passerelle multi-modèles, routage possible
          hors UE).
        </p>
        <p>
          Lorsqu'un fournisseur <strong>européen</strong> est utilisé (Mistral AI, hébergé dans
          l'UE) ou un modèle <strong>local</strong> (Ollama, exécuté sur notre propre serveur),
          aucun transfert hors UE n'a lieu.
        </p>
        <p>
          Lorsqu'un transfert hors UE a lieu, il est encadré par les clauses contractuelles types de
          la Commission européenne et/ou les mécanismes de conformité propres à chaque fournisseur.
          En configuration par défaut, le service utilise un modèle hébergé localement (Ollama) : le
          contenu des cours ne quitte pas notre infrastructure et aucun transfert hors UE n'a lieu
          (voir la décision ADR-0001).
        </p>
        <p>
          Vous pouvez nous demander quelle configuration LLM est active en nous contactant (voir
          rubrique 10).
        </p>
      </>
    ),
  },
  {
    title: 'Vos droits',
    hint: 'accès, rectification, suppression, portabilité, opposition, et comment les exercer.',
    content: (
      <>
        <p>
          Conformément aux articles 15 à 21 du RGPD, vous disposez des droits suivants, exerçables
          ainsi :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>Droit d'accès et de rectification</strong> : consultez et modifiez votre nom,
            prénom et email depuis la page « Mon profil ».
          </li>
          <li>
            <strong>Droit à la portabilité</strong> (art. 20) : utilisez le bouton{' '}
            <strong>« Exporter mes données »</strong> de la page « Mon profil » ; vous recevez par
            email un lien de téléchargement (valable 1 heure) d'un fichier JSON contenant l'ensemble
            de vos données.
          </li>
          <li>
            <strong>Droit à l'effacement</strong> (art. 17) : supprimez définitivement votre compte
            et toutes vos données depuis la <strong>Zone de danger</strong> de la page « Mon profil
            » (action irréversible).
          </li>
          <li>
            <strong>Droit d'opposition et de limitation</strong> : contactez-nous (rubrique 10).
          </li>
        </ul>
        <p>
          Pour tout droit non exerçable directement dans l'application, contactez le référent
          données.
        </p>
      </>
    ),
  },
  {
    title: 'Cookies',
    hint: 'renvoi vers la politique de cookies du site.',
    content: (
      <p>
        Le service n'utilise que des cookies et stockages strictement techniques (session
        applicative, token d'authentification). Aucun traceur publicitaire ou de mesure d'audience
        n'est déposé. Pour le détail, consultez notre{' '}
        <Link to="/legal/cookies" className="text-indigo-600 hover:underline">
          Politique de gestion des cookies
        </Link>
        .
      </p>
    ),
  },
  {
    title: 'Contact & réclamation',
    hint: 'email du référent données + droit de réclamation auprès de la CNIL.',
    content: (
      <>
        <p>
          Pour exercer vos droits ou pour toute question relative à vos données :{' '}
          dpo@edututor-ipssi.fr.
        </p>
        <p>
          Si vous estimez, après nous avoir contactés, que vos droits ne sont pas respectés, vous
          pouvez introduire une réclamation auprès de la <strong>CNIL</strong> (Commission nationale
          de l'informatique et des libertés), 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07,
          France —{' '}
          <a
            href="https://www.cnil.fr"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:underline"
          >
            www.cnil.fr
          </a>
          .
        </p>
      </>
    ),
  },
];

export default function ConfidentialitePage() {
  return (
    <LegalScaffold
      title="Politique de confidentialité"
      intro="Comment les données personnelles des utilisateurs sont collectées, utilisées et protégées (RGPD)."
      sections={SECTIONS}
      updatedAt="1er juillet 2026"
    />
  );
}
