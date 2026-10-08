# Narcisse

Ce qu’Internet sait de toi, et comment le réduire.

Tu décris qui tu es (noms, pseudos, emails, téléphones, domaines…). Narcisse cherche les traces
publiques de cette identité, les relie dans un graphe pour montrer comment elles s’enchaînent,
évalue ce que chacune expose, et t’aide à faire le ménage : supprimer un compte, demander un
déréférencement, envoyer une demande RGPD. Puis il suit tes progrès d’un scan à l’autre.

> **En construction.** Les fondations sont là : profils, scans de longue durée suivis en direct,
> reprise après fermeture du navigateur ou redémarrage. Aucune source réelle n’est encore branchée :
> seul un module de démonstration, qui invente des résultats sans rien interroger, permet d’essayer.
> Le [journal des changements](CHANGELOG.md) dira quand la première version sortira.

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
- **Poli avec les sites.** Il respecte `robots.txt`, limite son débit par site et s’annonce avec un
  User-Agent honnête.
- **Jamais de contournement.** Pas de connexion à ta place, pas de captcha résolu, pas de paywall
  franchi, pas de faux compte.
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

Le navigateur s’ouvre sur <http://narcisse.localhost:8765> : une adresse que les navigateurs
envoient d’eux-mêmes vers ta machine, sans réglage. En mode démo, crée un profil fictif (« Jeanne Exemple »), ajoute un
nom, un pseudo, un email et un domaine, puis lance un scan avec le module de démonstration : les
résultats arrivent au fil de l’eau pendant une trentaine de secondes, avec une limite de débit, une
erreur réseau rattrapée seule et une panne à relancer. Tu peux mettre en pause, annuler, fermer le
navigateur ou arrêter Narcisse : tout reprend où ça en était.

- `narcisse serve` : sans `--demo`, le module de démonstration n’est pas proposé. Les données du
  mode démo sont rangées à part : les profils fictifs ne se mélangent jamais aux vrais.
- `narcisse paths` : où sont rangées tes données (le dossier de données de ton système, jamais le
  dossier du projet) et le journal.

## Ajouter une source

Une source est un fichier dans `src/narcisse/modules/`, avec une classe qui décrit ce qu’elle fait
(titre, description, types d’éléments acceptés et produits, sites contactés, limite de débit,
licence) et une méthode qui rend ses résultats un par un. Le moteur s’occupe du reste : file
d’attente, pause, reprise, erreurs, limites de débit, affichage. Le module de démonstration,
[`demo.py`](src/narcisse/modules/demo.py), sert d’exemple.

## Contribuer

Les règles du dépôt (commandes, commits, confidentialité, invariants) : [CLAUDE.md](CLAUDE.md).

## Licence

[GPL-3.0](LICENSE).
