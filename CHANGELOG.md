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
  - clés PGP publiques publiées pour un email.
- Chaque recherche fait son bilan : vérifiés, trouvés, indéterminés, bloqués par un anti-robot,
  injoignables.
- Trier chaque trace : « c’est moi » ou « pas moi ». Le choix tient d’un scan à l’autre et les « pas
  moi » sont masqués (une case les fait revenir).
- Une page « Sources » qui dit ce que chaque source interroge, à quel rythme et sous quelle
  licence, et une page « Réglages » (token GitHub facultatif, sites adultes).

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
  scans en pause, de le faire démarrer avec Windows, de le redémarrer ou de le quitter ; une
  notification prévient quand un scan se termine ou qu’une recherche échoue.
- Narcisse s’installe comme une appli depuis Chrome ou Edge.
- Narcisse s’ouvre sur http://narcisse.localhost, sans numéro de port, une adresse que les navigateurs envoient
  d’eux-mêmes vers ta machine.
