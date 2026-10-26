// What the user can do about a trace, as the action sheet says it: the actions the API picks
// (remediation/actions.py) explained in French, the difficulty the knowledge base gives, and the
// e-mail link that opens a prepared request in the user's own mail client. Pure functions,
// tested in remediation.test.ts.
import type { Difficulty } from './types';

export interface ActionText {
  title: string;
  what: string;
}

export const ACTION_TEXTS: Record<string, ActionText> = {
  delete_account: {
    title: 'Supprimer le compte',
    what: 'Va sur la page de suppression du site, connecté à ton compte.',
  },
  delete_account_unknown: {
    title: 'Supprimer le compte',
    what: 'Narcisse ne connaît pas ce site : cherche « supprimer mon compte » dans ses réglages. S’il n’y en a pas, écris-lui.',
  },
  cannot_delete: {
    title: 'Le site ne permet pas de supprimer le compte',
    what: 'Demande-lui d’effacer tes données : le RGPD l’oblige à te répondre sous un mois.',
  },
  ask_site: {
    title: 'Demander au site d’effacer la page',
    what: 'Écris au responsable du site (mentions légales, page « données personnelles »).',
  },
  dereference: {
    title: 'Faire déréférencer la page',
    what: 'Même si la page reste, les moteurs de recherche peuvent cesser de la montrer quand on cherche ton nom. Colle le texte préparé dans leur formulaire.',
  },
  broker_opt_out: {
    title: 'Te faire retirer de ce courtier',
    what: 'Ce site revend des coordonnées. Demande ton retrait et oppose-toi au traitement de tes données.',
  },
  directory_objection: {
    title: 'T’opposer à la republication du registre',
    what: 'Ce site republie les données du registre des entreprises. Oppose-toi ; si tu es entrepreneur individuel, passe aussi ta fiche INSEE en diffusion partielle : les sites qui la reprennent suivent.',
  },
  archive_removal: {
    title: 'Retirer les copies archivées',
    what: 'L’Internet Archive retire des captures sur demande, une fois prouvé que tu en es l’auteur.',
  },
  keyserver_hide: {
    title: 'Retirer ton adresse du serveur de clés',
    what: 'Le serveur t’envoie un lien de confirmation par email.',
  },
  secure_leak: {
    title: 'Rendre la fuite inoffensive',
    what: 'Une fuite ne s’efface pas. Change le mot de passe de ce site et partout où tu l’as réutilisé, active la double authentification, et vérifie tes mots de passe dans la page « Mot de passe ».',
  },
  commit_email: {
    title: 'Ne plus publier ton adresse dans tes commits',
    what: 'Utilise l’adresse « noreply » de GitHub pour tes prochains commits. Les anciens la gardent, sauf à réécrire l’historique de tes dépôts.',
  },
  certificate_email: {
    title: 'Une adresse dans un certificat',
    what: 'Les journaux de certificats sont publics et ne s’effacent pas. Ne mets plus d’adresse personnelle dans tes prochains certificats.',
  },
  phone_opposition: {
    title: 'Limiter l’usage de ton numéro',
    what: 'Inscris-le sur Bloctel contre le démarchage, et demande la liste rouge à ton opérateur pour qu’il ne paraisse dans aucun annuaire.',
  },
  restrict_subdomain: {
    title: 'Fermer ou protéger ce sous-domaine',
    what: 'Retire l’enregistrement DNS s’il ne sert plus, ou mets le service derrière un VPN ou une authentification. Les journaux de certificats le garderont : un certificat générique (*.ton-domaine) évite d’en publier d’autres.',
  },
  whois_privacy: {
    title: 'Masquer tes coordonnées dans l’annuaire des domaines',
    what: 'Demande à ton bureau d’enregistrement (registrar) de masquer tes données personnelles. Pour un .fr, c’est le cas par défaut pour un particulier : vérifie ta fiche.',
  },
  registry_diffusion: {
    title: 'Limiter ce que publie le registre',
    what: 'Si tu es entrepreneur individuel, l’INSEE peut passer ta fiche en diffusion partielle (avec FranceConnect). Les annonces du BODACC sont des publications légales : elles restent, mais tu peux en demander le déréférencement.',
  },
  keep_professional: {
    title: 'À garder : attendu pour un profil pro',
    what: 'C’est ce qu’un profil pro montre normalement. Vérifie juste qu’il n’en dit pas plus que nécessaire.',
  },
};

export function actionText(code: string): ActionText {
  return ACTION_TEXTS[code] ?? { title: code, what: '' };
}

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  easy: 'Facile',
  medium: 'Moyen',
  hard: 'Difficile',
  limited: 'Limité',
  impossible: 'Impossible',
};

export const LETTER_LABELS: Record<string, string> = {
  erasure: 'Demande d’effacement (RGPD, art. 17)',
  objection: 'Opposition (RGPD, art. 21)',
  account_deletion: 'Demande de suppression du compte',
  archive: 'Demande de retrait à l’Internet Archive',
  dereference: 'Texte pour le formulaire de déréférencement',
};

/** Past this length, some mail clients cut the link: the text goes through the clipboard. */
export const MAILTO_LIMIT = 1800;

/** A `mailto:` link with the recipient, the subject and (when it fits) the body. Line breaks
 * are CRLF, as RFC 6068 asks. */
export function mailtoHref(to: string, subject: string, body: string): string {
  const enc = (text: string) => encodeURIComponent(text.replace(/\r?\n/g, '\r\n'));
  const head = `mailto:${enc(to.trim()).replace(/%40/g, '@')}?subject=${enc(subject)}`;
  const full = `${head}&body=${enc(body)}`;
  return full.length <= MAILTO_LIMIT ? full : head;
}

/** The letter as one text, to paste anywhere. */
export const letterText = (subject: string, body: string) =>
  subject ? `Objet : ${subject}\n\n${body}` : body;
