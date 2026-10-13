# Nouveautés

Les changements de chaque version de Narcisse, la plus récente en premier. Les numéros suivent le
[versionnage sémantique](https://semver.org/lang/fr/) : tant qu’ils commencent par 0, l’outil évolue
encore beaucoup.

## En préparation

Pas encore de version : la 0.1.0 sortira quand Narcisse sera utilisable sur de vraies sources.

### Déjà en place

- Premières vraies sources :
  - comptes par pseudo, sur plus de 600 sites de la liste WhatsMyName (les sites adultes sont
    vérifiés et signalés, ou exclus dans les réglages) ;
  - GitHub : profil public et emails visibles dans les commits ; pour un email, les comptes qui
    l’utilisent ;
  - Gravatar : profil public et comptes listés ;
  - clés PGP publiques publiées pour un email ;
  - GitLab (gitlab.com, framagit.org, salsa.debian.org, GNOME, freedesktop.org) : profil et emails
    des commits récents ;
  - Bluesky : profil et liens de la description ; un domaine servant de pseudo est vérifié ;
  - Mastodon et le Fediverse : compte sur une quinzaine de grandes instances et celles ajoutées dans
    les réglages, ou un pseudo@instance sur la sienne ; les liens vérifiés par Mastodon ;
  - Hacker News, Stack Exchange (avec ses homonymes) et Keybase (preuves d’identité).
- Ce que disent tes domaines :
  - leur enregistrement (RDAP, ou WHOIS pour .eu, .de, .be, .io…) : chez qui, depuis quand, et les
    coordonnées du titulaire quand le registre les publie, ou le fait qu’il les masque ;
  - leur DNS : qui reçoit les emails, qui héberge le site, les services auprès desquels le domaine
    a été vérifié (Google, Microsoft, Facebook, Apple…), les adresses que citent ses enregistrements ;
  - leurs sous-domaines, publiés dans les journaux de certificats (crt.sh, ou Cert Spotter quand
    crt.sh ne répond pas) ;
  - leur site : mentions légales, pages contact et « à propos » (nom, adresse, téléphone, email,
    SIREN, liens vers des profils), dans le respect de `robots.txt`.
- Ce que gardent les archives du web (Wayback Machine) : les pages archivées de ton site, dont un
  CV, une page contact ou des documents supprimés depuis, et depuis quand un profil est archivé.
- La recherche assistée : pour chaque élément, les recherches qui valent la peine sur Google, Bing,
  DuckDuckGo et Qwant, ouvertes dans ton navigateur (Narcisse n’interroge jamais un moteur) ; une
  page trouvée ainsi se colle en retour et rejoint tes traces.
- La recherche web pendant les scans, par ta propre instance SearXNG : `narcisse searxng`
  l’installe et la lance avec Docker, sur ta machine seulement.
- « Ajouter comme élément » : une trace trouvée (un domaine cité dans une bio, un compte…) devient
  un point de départ des scans suivants.
- Les liens et adresses d’une bio deviennent des traces (sur GitHub aussi).
- Chaque recherche fait son bilan : vérifiés, trouvés, indéterminés, bloqués par un anti-robot,
  injoignables.
- Le graphe d’un profil : chaque trace reliée à celle qui y a mené (un compte et ce qu’il affiche),
  qui se remplit pendant le scan ; recherche, filtres (type, source, statut, confiance, date),
  focus sur une trace et ses voisines, détail de ses preuves. La même chose en liste, avec la même
  sélection. En mode démo, des graphes fictifs de 500 à 20 000 traces.
- Explorer le graphe : comment deux traces sont reliées (le plus court chemin, jusqu’à toi en un
  clic), replier les traces isolées, regrouper par type, par source ou par site, une mini-carte,
  et des vues enregistrées (filtres, groupes, cadrage) pour y revenir.
- Trier chaque trace : « c’est moi » ou « pas moi ». Le choix tient d’un scan à l’autre et les « pas
  moi » sont masqués (une case les fait revenir).
- Une page « Sources » qui dit ce que chaque source interroge, à quel rythme et sous quelle
  licence, et une page « Réglages » (tokens GitHub et GitLab facultatifs, instances Mastodon,
  sites adultes).

- Profils (perso, pro ou les deux) et ce qui t’identifie : noms, pseudos, emails, téléphones,
  adresses, domaines, organisations, comptes. Chaque élément peut être surveillé ou ignoré.
- Scans de longue durée suivis en direct : les résultats arrivent un par un, chaque recherche dit
  où elle en est (en file, en cours, en pause, limitée par la source avec le temps d’attente, en
  erreur avec la raison et un bouton pour réessayer, terminée) et combien de temps il lui reste.
- Pause, reprise et annulation immédiates. Le navigateur peut être fermé et Narcisse redémarré :
  les scans reprennent où ils en étaient, sans perdre ni doubler un résultat.
- Centre d’activité accessible depuis chaque écran.
- Thème clair, sombre ou celui du système ; animations réduites si le système le demande.
- Tout reste sur ta machine : Narcisse n’écoute que sur 127.0.0.1 et refuse les requêtes d’autres
  sites ouverts dans le navigateur.
- Mode démo, avec un module qui invente des résultats sans rien interroger, et ses données rangées à
  part.
- Sous Windows, Narcisse s’ajoute au menu Démarrer : un clic l’ouvre dans sa propre fenêtre, en le
  démarrant au besoin. Une icône près de l’horloge montre ce qui se passe et permet de mettre les
  scans en pause, de passer du mode démo à tes vraies données (case « Mode démo », le dernier choix
  est gardé), de le faire démarrer avec Windows, de le redémarrer ou de le quitter ; une
  notification prévient quand un scan se termine ou qu’une recherche échoue.
- Narcisse s’installe comme une appli depuis Chrome ou Edge.
- Narcisse s’ouvre sur http://narcisse.localhost, sans numéro de port, une adresse que les navigateurs envoient
  d’eux-mêmes vers ta machine.
