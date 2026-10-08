# Narcisse

Ce qu’Internet sait de toi, et comment le réduire.

Tu décris qui tu es (noms, pseudos, emails, téléphones, domaines…). Narcisse cherche les traces
publiques de cette identité, les relie dans un graphe pour montrer comment elles s’enchaînent,
évalue ce que chacune expose, et t’aide à faire le ménage : supprimer un compte, demander un
déréférencement, envoyer une demande RGPD. Puis il suit tes progrès d’un scan à l’autre.

> **En construction.** Narcisse n’est pas encore utilisable : les fondations (scans de longue durée,
> suivi en direct, profils) se mettent en place, et aucune source réelle n’est branchée. Le
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
- **Poli avec les sites.** Il respecte `robots.txt`, limite son débit par site et s’annonce avec un
  User-Agent honnête.
- **Jamais de contournement.** Pas de connexion à ta place, pas de captcha résolu, pas de paywall
  franchi, pas de faux compte.
- **Rien n’est envoyé à ta place.** Narcisse prépare les demandes de suppression ; c’est toujours
  toi qui les envoies.
- **Gratuit.** Aucune API payante ; un token gratuit (GitHub, par exemple) peut lever des limites,
  mais rien ne l’exige.

## Contribuer

Les règles du dépôt (commandes, commits, confidentialité, invariants) : [CLAUDE.md](CLAUDE.md).

## Licence

[GPL-3.0](LICENSE).
