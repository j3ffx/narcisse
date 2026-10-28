# Narcisse

Ce qu’Internet sait de toi, et comment le réduire.

Tu décris qui tu es (noms, pseudos, emails, téléphones, domaines…). Narcisse cherche les traces
publiques de cette identité, les relie dans un graphe pour montrer comment elles s’enchaînent,
évalue ce que chacune expose, et t’aide à faire le ménage : supprimer un compte, demander un
déréférencement, envoyer une demande RGPD. Puis il suit tes progrès d’un scan à l’autre.

> **Première version.** Narcisse cherche tes comptes à partir d’un pseudo (plus de 600 sites),
> lit tes profils publics (GitHub, GitLab, Bluesky, Mastodon, Hacker News, Stack Exchange, Keybase),
> ce que Gravatar et les serveurs de clés PGP publient sur toi, ce que disent tes domaines (registre,
> DNS, certificats, mentions légales de ton site), ce qu’en gardent les archives du web, les fuites
> où figure ton email et les registres d’entreprises, et te prépare les recherches à faire sur les
> moteurs. Il relie tout dans un graphe, te dit pour chaque trace à quel point c’est toi et à quel
> point elle t’expose (en expliquant pourquoi), te dit quoi faire de chacune (avec les demandes RGPD
> prêtes à envoyer) et suit tes demandes jusqu’à ce que la trace disparaisse. Ce que chaque version
> apporte : le [journal des changements](CHANGELOG.md).

![Le graphe d’un profil fictif en mode démo : une trace sélectionnée et le chemin qui la relie à
l’identité, le reste atténué, la mini-carte et le détail de la trace](docs/capture-graphe.png)

## Pour qui, pour quoi

Narcisse est fait pour **se chercher soi-même**, ou chercher quelqu’un qui te l’a **demandé
explicitement** (un proche que tu aides, un client d’un audit d’exposition, avec son accord écrit).

Il n’est pas fait pour enquêter sur autrui. Sont exclus, entre autres : chercher une personne
à son insu, la surveiller, la harceler, réunir des informations pour la retrouver, l’usurper ou la
discréditer. Ces usages sont souvent illégaux, et toujours contraires à l’esprit du projet.

## Le cadre légal

- Une information publique reste une **donnée personnelle**. En Europe, le RGPD s’applique dès
  qu’on collecte et organise des données sur une personne identifiable, même trouvées en ligne.
  L’usage sur soi-même relève de la sphère personnelle ; dès que d’autres personnes sont concernées,
  il te faut une base légale (leur consentement, en pratique).
- Hors de l’Union européenne, d’autres lois s’appliquent : vérifie celles de ton pays.
- Les conditions d’utilisation des sites interrogés s’appliquent aussi : Narcisse s’en tient aux
  accès publics prévus par chaque service.

## Comment Narcisse se comporte

- **Tout reste sur ta machine.** Narcisse tourne en local et n’écoute que sur `127.0.0.1`. Pas de
  compte, pas de serveur distant, aucune télémétrie. Les seules requêtes qui sortent vont vers les
  sources interrogées (et vers le LLM que tu auras choisi, si tu en configures un).
- **Passif.** Il lit des API et des pages publiques, des archives et des registres ouverts. Il ne
  sollicite jamais un service pour deviner si tu y as un compte, ne se connecte nulle part et ne
  remplit aucun formulaire.
- **Poli avec les sites.** Pour savoir si un compte existe, il demande une seule page par site ;
  quand il parcourt des pages de lien en lien, il respecte `robots.txt`. Il limite son débit par
  site et s’annonce toujours avec un User-Agent honnête, jamais comme un navigateur.
- **Jamais de contournement.** Pas de connexion à ta place, pas de captcha résolu (les sites
  protégés ne sont pas interrogés, une page anti-robot vaut « je ne sais pas »), pas de paywall
  franchi, pas de faux compte, jamais la clé d’API de quelqu’un d’autre.
- **Rien n’est envoyé à ta place.** Narcisse prépare les demandes de suppression ; c’est toujours
  toi qui les envoies.
- **Gratuit.** Aucune API payante ; un token gratuit (GitHub, par exemple) peut lever des limites,
  mais rien ne l’exige.

## Installer

Il te faut [uv](https://docs.astral.sh/uv/getting-started/installation/), qui installe aussi
Python s’il manque. Puis, dans un terminal :

```bash
uv tool install https://github.com/j3ffx/narcisse/releases/download/v0.1.0/narcisse-0.1.0-py3-none-any.whl
```

(Pour une version plus récente, prends le lien du fichier `.whl` sur la page des
[versions](https://github.com/j3ffx/narcisse/releases).) Ensuite :

```bash
narcisse serve --demo
```

- **Mettre à jour** : la même commande avec le lien de la nouvelle version et `--force`, puis
  « Redémarrer » dans le menu de l’icône de Narcisse.
- **Désinstaller** : `uv tool uninstall narcisse`. Tes données restent dans leur dossier
  (`narcisse paths` te dit où) : supprime-le si tu veux tout effacer.
- **Depuis les sources** (pour contribuer) : il faut aussi [Node.js](https://nodejs.org/) 22 ou
  plus. `git clone https://github.com/j3ffx/narcisse.git`, puis dans le dossier `npm ci`,
  `npm run build` et `uv run narcisse serve --demo`. Les règles du dépôt sont dans
  [CLAUDE.md](CLAUDE.md).

## Premiers pas

Le navigateur s’ouvre sur <http://narcisse.localhost> : une adresse que les navigateurs
envoient d’eux-mêmes vers ta machine, sans réglage. En mode démo, crée un profil fictif (« Jeanne Exemple »), ajoute un
nom, un pseudo, un email et un domaine, puis lance un scan avec le module de démonstration : les
résultats arrivent au fil de l’eau pendant une trentaine de secondes, avec une limite de débit, une
erreur réseau rattrapée seule et une panne à relancer. Tu peux mettre en pause, annuler, fermer le
navigateur ou arrêter Narcisse : tout reprend où ça en était.

Le profil s’ouvre sur son **graphe** : chaque trace y apparaît au fil du scan, reliée à celle qui y a
mené (un pseudo → un compte → le site indiqué sur ce compte), d’autant plus grosse qu’elle t’expose.
Clique une trace pour voir ses scores et leurs raisons, ses preuves et ses voisines, cherche-en une
(touche `/`), filtre par type, source, statut, confiance, risque ou date,
demande comment deux traces sont reliées (le plus court chemin), replie les traces isolées,
regroupe par type, par source ou par site, et enregistre la vue pour y revenir. La
vue **Liste** montre les mêmes traces, avec les mêmes filtres et la même sélection, sous une forme
que tout le monde peut lire. En mode démo, le bouton « Graphe fictif » crée un profil de 500 à
20 000 traces inventées, pour voir le graphe à grande échelle.

- `narcisse serve` : sans `--demo`, le module de démonstration n’est pas proposé. Les données du
  mode démo sont rangées à part : les profils fictifs ne se mélangent jamais aux vrais.
- `narcisse paths` : où sont rangées tes données (le dossier de données de ton système, jamais le
  dossier du projet) et le journal.

### Comme une appli (Windows)

```powershell
narcisse shortcut --demo
```

(Sans `--demo`, il s’ouvre directement sur tes vraies données.)

Narcisse apparaît dans le menu Démarrer (tape « Narcisse », ou épingle-le). Un clic l’ouvre dans sa
propre fenêtre, en le démarrant d’abord s’il ne tourne pas. Il se range alors près de l’horloge :
l’icône dit ce qui se passe (un point bleu pendant un scan, jaune en pause, rouge si une recherche
échoue), et son menu permet d’ouvrir Narcisse, de mettre les scans en pause, de couper les
notifications, de passer du mode démo à tes vraies données et inversement (case « Mode démo » : le
menu Démarrer et le démarrage avec Windows rouvrent ensuite le dernier choisi), de le faire démarrer
avec Windows (décoché tant que tu ne le coches pas), de le redémarrer ou de le quitter. Une notification te prévient quand un scan se termine ou qu’une
recherche échoue.

Pour l’installer comme une appli du navigateur (icône dans la barre des tâches), ouvre
<http://narcisse.localhost> dans Chrome ou Edge et clique sur l’icône d’installation dans la barre
d’adresse.

Depuis les sources, mettre à jour : `git pull`, puis `npm run build`, puis « Redémarrer » dans le
menu de l’icône.

### Une adresse encore plus courte (facultatif)

Pour ouvrir Narcisse sur <http://narcisse/>, ajoute une ligne au fichier `hosts` de ton système :
`127.0.0.1 narcisse`. Sous Windows, dans un PowerShell lancé en administrateur :

```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "127.0.0.1 narcisse"
```

Sous macOS ou Linux : `echo "127.0.0.1 narcisse" | sudo tee -a /etc/hosts`. Relance ensuite
Narcisse : il voit la ligne et répond aussi à cette adresse. Sans elle, il refuse ce nom, qui
pourrait sinon être détourné par un réseau mal intentionné. Dans le navigateur, tape `narcisse/` (avec
la barre oblique) la première fois ; ensuite, il la propose de lui-même.

## Les sources

| Source                                  | À partir de                                           | Ce qu’elle trouve                                                                                                                                                                                                                           |
| --------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Comptes par pseudo (liste WhatsMyName)  | un pseudo                                             | les comptes à ce nom sur plus de 600 sites (réseaux sociaux, jeux, code, forums, sites adultes signalés comme tels)                                                                                                                         |
| GitHub                                  | un pseudo, un email                                   | le profil public et les emails visibles dans les commits ; pour un email, les comptes qui l’utilisent                                                                                                                                       |
| Gravatar                                | un email                                              | le profil public et les comptes qu’il liste (seule l’empreinte de l’email est envoyée)                                                                                                                                                      |
| Clés PGP publiques (keys.openpgp.org)   | un email                                              | une clé publiée, et les noms et adresses qu’elle porte                                                                                                                                                                                      |
| GitLab                                  | un pseudo, un compte                                  | le profil sur gitlab.com, framagit.org, salsa.debian.org, GNOME et freedesktop.org, et les emails des commits récents                                                                                                                       |
| Bluesky                                 | un pseudo, un domaine, un compte                      | le profil, sa description et ses liens ; un domaine servant de pseudo est vérifié par Bluesky                                                                                                                                               |
| Mastodon et Fediverse                   | un pseudo, un pseudo@instance, un compte              | le compte sur une quinzaine de grandes instances et celles que tu ajoutes ; les liens que Mastodon a vérifiés                                                                                                                               |
| Hacker News                             | un pseudo, un compte                                  | le compte, son ancienneté, et les liens et adresses de sa présentation                                                                                                                                                                      |
| Stack Exchange                          | un pseudo, un nom                                     | les utilisateurs de Stack Overflow qui portent exactement ce nom (des homonymes sont possibles) et leurs comptes sur le réseau                                                                                                              |
| Keybase                                 | un pseudo, un domaine, un compte                      | le compte et ses preuves d’identité, qui relient sûrement d’autres comptes et des domaines                                                                                                                                                  |
| Enregistrement du domaine (RDAP, WHOIS) | un domaine                                            | le bureau d’enregistrement et les dates, et les nom, email, téléphone et adresse du titulaire quand le registre les publie (ou le fait qu’il les masque)                                                                                    |
| DNS du domaine                          | un domaine                                            | qui reçoit ses emails, qui l’héberge, les services auprès desquels il a été vérifié, les adresses citées par ses enregistrements (via le résolveur de ta machine)                                                                           |
| Certificats (crt.sh, Cert Spotter)      | un domaine                                            | ses sous-domaines (`nas.`, `vpn.`, `cloud.`…) publiés dans les journaux de certificats                                                                                                                                                      |
| Site du domaine                         | un domaine                                            | ce que disent ses mentions légales, ses pages contact et « à propos » : nom, adresse, téléphone, email, SIREN, liens vers des profils (dans le respect de `robots.txt`)                                                                     |
| Archives du web (Wayback Machine)       | un domaine, un compte                                 | les pages archivées du site (dont un CV, une page contact ou « à propos », des documents, même supprimés depuis) et depuis quand un profil est archivé                                                                                      |
| Recherche web (ton instance SearXNG)    | un nom, un pseudo, un email, un téléphone, un domaine | les pages qui les citent exactement, trouvées par ton instance SearXNG (facultatif, voir plus bas)                                                                                                                                          |
| Fuites de données (XposedOrNot)         | un email                                              | les fuites connues où il figure : quand, quelles données (mots de passe, adresses, dates de naissance…), si les mots de passe étaient lisibles ; l’adresse est envoyée à XposedOrNot                                                        |
| Registres d’entreprises (France)        | un nom, une organisation, un SIREN                    | les entreprises que tu diriges ou as dirigées, ou à ton nom : le registre publie le mois et l’année de naissance des dirigeants et le siège, souvent le domicile ; pour une entreprise, ses dirigeants, son siège et ses annonces au BODACC |
| Numéro de téléphone                     | un téléphone                                          | ce qu’il dit de lui-même, sans rien demander à personne : mobile ou fixe, pays, région, opérateur d’origine                                                                                                                                 |

Chaque recherche dit ce qu’elle a pu vérifier : par exemple « 640 vérifiés · 12 trouvés · 109
bloqués par un anti-robot ». Le détail de chaque source (sites contactés, rythme, licence) est dans
la page « Sources » de Narcisse. Dans les réglages, un token GitHub personnel gratuit relève la
limite de GitHub de 60 à 5 000 requêtes par heure, et un token GitLab gratuit ajoute la bio, le lieu
et le site des profils de gitlab.com ; rien ne les exige. Tu peux aussi y ajouter tes instances
Mastodon : seules les instances de la liste sont contactées.

### Un mot de passe a-t-il fuité ?

La page « Mot de passe » vérifie s’il apparaît dans les fuites que recense Pwned Passwords, sans
qu’il quitte la page : elle en calcule l’empreinte, n’en envoie que les 5 premiers caractères, et
compare elle-même la réponse. Rien n’est gardé.

### Les moteurs de recherche

Narcisse n’interroge jamais Google, Bing ou un autre moteur lui-même. L’onglet « Recherche » d’un
profil te prépare les recherches qui valent la peine pour chacun de tes éléments (un nom dans des
documents et des registres d’entreprises, un email dans des listes, un numéro écrit de plusieurs
façons…) et les ouvre dans ton navigateur ; une page qui parle de toi, tu la colles en retour et
elle rejoint tes traces.

Si tu veux que les scans cherchent aussi sur le web, installe ta propre instance de
[SearXNG](https://docs.searxng.org/) (un métamoteur qui tourne chez toi) avec Docker :

```bash
narcisse searxng
```

La commande écrit sa configuration dans ton dossier de configuration (avec une clé secrète qui lui
est propre), la lance sur `127.0.0.1:8888` et règle son adresse dans Narcisse. C’est elle qui
interroge les moteurs, comme le ferait ton navigateur.

### Confiance, risque et pistes

Chaque trace a deux scores sur 100, avec leurs raisons dans son détail (« Pourquoi ces scores ? ») :

- la **confiance** (« est-ce toi ? ») part de ce qu’en dit la source, monte quand plusieurs sources
  indépendantes la trouvent ou qu’elle relie plusieurs de tes éléments, baisse beaucoup quand on ne
  l’a trouvée qu’à travers des traces que tu as rejetées. « C’est moi » la met à 100, « pas moi » à
  0, et les traces voisines suivent ;
- le **risque** (« à quel point ça t’expose ? ») dépend du type de trace (une adresse postale
  expose plus qu’un pseudo) et de ce qu’elle révèle : mots de passe lisibles dans une fuite, date
  de naissance au registre, courtier en données, site adulte, Strava, sous-domaine comme `nas.` ou
  `vpn.`, coordonnées publiées par le registre d’un domaine, copie dans une archive… Pour un
  profil pro (ou perso et pro), ce qu’il est normal de montrer (ton entreprise, ton domaine, le
  registre) compte moitié moins. Il est pondéré par la confiance, et classé faible, moyen, élevé
  ou critique.

Un scan part des éléments de ton profil. Les **pistes**, dans l’onglet Éléments, sont les traces
assez sûres pour qu’un scan parte aussi d’elles (un email lu dans un profil, un domaine cité dans
une bio…) : « Ajouter comme élément » ou « Écarter ». Si tu le choisis pour ce profil, les scans
suivent eux-mêmes les plus sûres, à un ou deux sauts, 25 au plus par scan, jamais une trace que tu
as rejetée.

En mode démo, seul le module de démonstration est proposé : des identités fictives n’interrogent
jamais de vrais sites.

### Que faire de chaque trace

Le détail d’une trace dit ce que tu peux faire, le plus utile d’abord : supprimer un compte (la
page de suppression du site et sa difficulté, d’après JustDeleteMe), demander à un site d’effacer
une page, la faire déréférencer des moteurs de recherche (formulaires de Google, Bing et Qwant),
te faire retirer d’un courtier en données ou d’un annuaire d’entreprises, retirer des copies de la
Wayback Machine, masquer tes coordonnées dans l’annuaire des domaines, passer ta fiche INSEE en
diffusion partielle, rendre une fuite inoffensive…

Pour écrire, Narcisse prépare la demande (effacement ou opposition au titre du RGPD, suppression de
compte, déréférencement), en français ou en anglais, signée avec les éléments de ton profil (nom,
email, adresse) et des « [à compléter] » pour le reste. Tu la relis, tu la modifies, puis tu la
copies ou tu l’ouvres dans ta messagerie : **Narcisse n’envoie jamais rien**. Sans réponse sous un
mois, la page renvoie vers la plainte à la CNIL.

« Je l’ai envoyée » (ou « Ajouter à « À faire » ») fait suivre l’action dans l’onglet **À faire**
du profil : son statut (à faire, envoyée, en attente, faite, refusée), la relance prête un mois
après l’envoi (l’onglet le signale, et l’icône de Narcisse te le rappelle une fois par jour), et
« Vérifier maintenant », qui relance seulement les recherches qui avaient trouvé la trace. Tout
scan qui ne la retrouve plus la marque disparue et clôt la demande. En haut de l’onglet, ton
exposition : tes traces par niveau de risque, et son évolution scan après scan.

![Le détail d’une trace fictive en mode démo : « Que faire ? » propose de demander au site
d’effacer la page, avec la demande suivie, puis de la faire déréférencer](docs/capture-que-faire.png)

![L’onglet « À faire » d’un profil fictif : l’exposition par niveau de risque, une demande à
relancer et des demandes en cours](docs/capture-a-faire.png)

### Ce qui a changé, tes exports, ta sauvegarde

Une trace que plus aucun scan ne trouve (toutes les recherches qui l’avaient trouvée sont
repassées sans erreur, sans la revoir) est marquée **disparue** : grisée dans le graphe et la
liste, sortie de ton exposition, et de retour si un scan la retrouve. L’onglet **Scans** compare
deux scans terminés : les traces nouvelles, disparues, modifiées (la page a changé), et celles
qu’on ne peut pas dire disparues parce que leurs recherches ne sont pas toutes repassées.

Un profil peut se **relancer tout seul** chaque semaine ou chaque mois (onglet Éléments) : tant
que Narcisse tourne (« Démarrer avec Windows » dans le menu de son icône pour qu’il tourne
toujours), il relance un scan avec les sources cochées par défaut, et un ordinateur éteint le
rattrape au démarrage. À la fin de chaque scan, sa page et la notification disent ce qui a changé
(« 3 nouvelles traces, 1 disparue »). Pour cron ou le Planificateur de tâches, `narcisse scan`
lance les scans programmés dus (ou `--profil N` celui d’un profil), attend leur fin et le dit.
Au-dessus du graphe et de la liste, un **curseur** remonte le temps : les traces telles que
chaque scan les a laissées.

Le bouton **Exporter** d’un profil enregistre un rapport HTML à lire ou imprimer (sans script ni
ressource extérieure), ses traces en CSV pour un tableur, ou tout en JSON. Dans les **Réglages**,
« Télécharger une sauvegarde » met tous tes profils, demandes et réglages dans un fichier
`.narcisse`, chiffré si tu donnes une phrase de passe (il garde alors aussi tes tokens) ;
« Restaurer » le remet en place, après avoir gardé tes données du moment dans une sauvegarde de
sécurité. En ligne de commande, `narcisse backup [--chiffrer]` et `narcisse restore FICHIER` font
de même (le second, Narcisse arrêté).

## Ajouter une source

Une source est un fichier dans `src/narcisse/modules/`, avec une classe qui décrit ce qu’elle fait
(titre, description, types d’éléments acceptés et produits, sites contactés, limite de débit,
licence) et une méthode qui rend ses résultats un par un. Le moteur s’occupe du reste : file
d’attente, pause, reprise, erreurs, limites de débit, affichage. Le module de démonstration,
[`demo.py`](src/narcisse/modules/demo.py), sert d’exemple.

## Contribuer

Les règles du dépôt (commandes, commits, confidentialité, invariants) : [CLAUDE.md](CLAUDE.md).

## Crédits

- Liste des sites : [WhatsMyName](https://github.com/WebBreacher/WhatsMyName), Micah Hoffman et
  contributeurs, licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Copie
  adaptée (sites interrogés avec la clé d’un tiers retirés), provenance dans
  `src/narcisse/modules/data/wmn-source.json`.
- Pages de suppression des comptes : [JustDeleteMe](https://github.com/jdm-contrib/jdm), Robb
  Lewis, la JDM Contrib Team et contributeurs, licence MIT. Copie allégée (anglais et français),
  provenance et notice dans `src/narcisse/remediation/data/jdm-source.json`.
- Fuites de données : [XposedOrNot](https://xposedornot.com/), pour un usage personnel.
- Mots de passe : [Pwned Passwords](https://haveibeenpwned.com/Passwords), de Have I Been Pwned (Troy
  Hunt), licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Entreprises : [API Recherche d’entreprises](https://recherche-entreprises.api.gouv.fr/) et
  [BODACC](https://www.bodacc.fr/) (DILA), données publiques de l’État, Licence Ouverte.
- Téléphones : [libphonenumber](https://github.com/google/libphonenumber) (Google), licence
  Apache 2.0.
- Serveurs RDAP et WHOIS, bureaux d’enregistrement : données publiques de
  l’[IANA](https://www.iana.org/domains/root/db), copie datée dans
  `src/narcisse/modules/data/registries-source.json`.

## Licence

[GPL-3.0](LICENSE).
