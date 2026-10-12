# Narcisse

Ce qu’Internet sait de toi, et comment le réduire.

Tu décris qui tu es (noms, pseudos, emails, téléphones, domaines…). Narcisse cherche les traces
publiques de cette identité, les relie dans un graphe pour montrer comment elles s’enchaînent,
évalue ce que chacune expose, et t’aide à faire le ménage : supprimer un compte, demander un
déréférencement, envoyer une demande RGPD. Puis il suit tes progrès d’un scan à l’autre.

> **En construction.** Narcisse cherche déjà tes comptes à partir d’un pseudo (plus de 600 sites),
> ce que GitHub, Gravatar et les serveurs de clés PGP publient sur toi, et te laisse trier chaque
> trace (« c’est moi » / « pas moi »). Le graphe, la remédiation et d’autres sources arrivent. Le
> [journal des changements](CHANGELOG.md) dira quand la première version sortira.

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
- **Passif par défaut.** Il lit des API et des pages publiques, des archives et des registres
  ouverts. Les techniques qui sollicitent un service sans s’y connecter (vérifier qu’un email est
  inscrit quelque part, par exemple) sont désactivées par défaut, une par une, et expliquées avant
  que tu les actives.
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

## Essayer

Il faut [uv](https://docs.astral.sh/uv/) (Python) et [Node.js](https://nodejs.org/) 22 ou plus,
le temps que Narcisse soit publié sous forme de paquet.

```bash
git clone https://github.com/j3ffx/narcisse.git
cd narcisse
npm ci
npm run build
uv run narcisse serve --demo
```

Le navigateur s’ouvre sur <http://narcisse.localhost> : une adresse que les navigateurs
envoient d’eux-mêmes vers ta machine, sans réglage. En mode démo, crée un profil fictif (« Jeanne Exemple »), ajoute un
nom, un pseudo, un email et un domaine, puis lance un scan avec le module de démonstration : les
résultats arrivent au fil de l’eau pendant une trentaine de secondes, avec une limite de débit, une
erreur réseau rattrapée seule et une panne à relancer. Tu peux mettre en pause, annuler, fermer le
navigateur ou arrêter Narcisse : tout reprend où ça en était.

- `narcisse serve` : sans `--demo`, le module de démonstration n’est pas proposé. Les données du
  mode démo sont rangées à part : les profils fictifs ne se mélangent jamais aux vrais.
- `narcisse paths` : où sont rangées tes données (le dossier de données de ton système, jamais le
  dossier du projet) et le journal.

### Comme une appli (Windows)

```powershell
uv run narcisse shortcut --demo
```

Narcisse apparaît dans le menu Démarrer (tape « Narcisse », ou épingle-le). Un clic l’ouvre dans sa
propre fenêtre, en le démarrant d’abord s’il ne tourne pas. Il se range alors près de l’horloge :
l’icône dit ce qui se passe (un point bleu pendant un scan, jaune en pause, rouge si une recherche
échoue), et son menu permet d’ouvrir Narcisse, de mettre les scans en pause, de couper les
notifications, de le faire démarrer avec Windows (décoché tant que tu ne le coches pas), de le
redémarrer ou de le quitter. Une notification te prévient quand un scan se termine ou qu’une
recherche échoue.

Pour l’installer comme une appli du navigateur (icône dans la barre des tâches), ouvre
<http://narcisse.localhost> dans Chrome ou Edge et clique sur l’icône d’installation dans la barre
d’adresse.

Mettre à jour : `git pull`, puis `npm run build`, puis « Redémarrer » dans le menu de l’icône.

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

| Source                                 | À partir de         | Ce qu’elle trouve                                                                                                   |
| -------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Comptes par pseudo (liste WhatsMyName) | un pseudo           | les comptes à ce nom sur plus de 600 sites (réseaux sociaux, jeux, code, forums, sites adultes signalés comme tels) |
| GitHub                                 | un pseudo, un email | le profil public et les emails visibles dans les commits ; pour un email, les comptes qui l’utilisent               |
| Gravatar                               | un email            | le profil public et les comptes qu’il liste (seule l’empreinte de l’email est envoyée)                              |
| Clés PGP publiques (keys.openpgp.org)  | un email            | une clé publiée, et les noms et adresses qu’elle porte                                                              |

Chaque recherche dit ce qu’elle a pu vérifier : par exemple « 640 vérifiés · 12 trouvés · 109
bloqués par un anti-robot ». Le détail de chaque source (sites contactés, rythme, licence) est dans
la page « Sources » de Narcisse. Un token GitHub personnel gratuit, dans les réglages, relève la
limite de GitHub de 60 à 5 000 requêtes par heure ; rien ne l’exige.

En mode démo, seul le module de démonstration est proposé : des identités fictives n’interrogent
jamais de vrais sites.

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

## Licence

[GPL-3.0](LICENSE).
