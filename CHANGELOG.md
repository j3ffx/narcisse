# Nouveautés

Les changements de chaque version de Narcisse, la plus récente en premier. Les numéros suivent le
[versionnage sémantique](https://semver.org/lang/fr/) : tant qu’ils commencent par 0, l’outil évolue
encore beaucoup.

## 0.4.0 (2026-10-30)

Narcisse parle anglais aussi.

- L’interface en français ou en anglais : la langue de ton navigateur, ou celle choisie dans les
  Réglages. Les preuves des nouveaux scans, les sources, les actions et les guides, l’export,
  l’icône, les notifications et la ligne de commande suivent ; les preuves des scans d’avant
  restent en français.
- L’assistant IA reçoit ses consignes et répond dans ta langue.
- Un README en anglais.

## 0.3.0 (2026-10-30)

Un assistant IA, si tu en veux un : il t’aide à trier tes traces, à les comprendre, à trouver des
pistes et à écrire tes lettres. Aucun par défaut, rien n’est appliqué sans ton clic, et tu vois
toujours ce qui part.

- Un assistant IA, si tu en choisis un dans les Réglages (aucun par défaut) : ton Claude Code,
  avec ton abonnement. Dans le détail d’une trace, « Est-ce bien moi ? » et « Expliquer cette
  trace » ; « Trier avec l’IA » pose la première question pour les traces pas encore triées.
  Chaque réponse est marquée « Avis de l’IA », rien n’est appliqué sans ton clic, et tu vois le
  texte exact envoyé avant l’envoi.
- L’assistant peut aussi être un modèle sur ta machine (Ollama, LM Studio, llama.cpp) : Narcisse
  te conseille un modèle selon ta mémoire et ta carte graphique, et le fait télécharger par Ollama
  sur ton clic. Ou n’importe quel service compatible OpenAI, avec sa clé.
- « Chercher des pistes » dans une trace : les emails, pseudos ou domaines écrits dans ses
  preuves, proposés dans Éléments → Pistes, jamais suivis sans toi.
- « Adapter avec l’IA » dans une lettre : ton contexte et ton ton, ton identité remplacée par des
  repères avant l’envoi, les articles de loi gardés.

## 0.2.0 (2026-10-28)

L’historique : ce qui a changé d’un scan à l’autre, des traces qui disparaissent, des scans qui se
relancent tout seuls, et tes données à emporter (exports, sauvegardes).

- Une trace que plus aucun scan ne trouve est marquée disparue : grisée dans le graphe et la
  liste (un filtre la masque), sortie de ton exposition, de retour si un scan la retrouve. Une
  demande n’est close que si toutes les recherches qui avaient trouvé sa trace sont repassées.
- Comparer deux scans : traces nouvelles, disparues, modifiées, et celles qu’on ne peut pas dire
  disparues.
- Exporter un profil : rapport HTML à lire ou imprimer, traces en CSV, tout en JSON.
- Relancer un profil tout seul, chaque semaine ou chaque mois, tant que Narcisse tourne (rattrapé
  au démarrage) ; `narcisse scan` pour cron ou le Planificateur de tâches.
- La fin d’un scan dit ce qui a changé depuis le précédent, sur sa page et dans la notification.
- Un curseur au-dessus du graphe et de la liste les montre tels que chaque scan les a laissés.
- Sauvegarder et restaurer toutes tes données (Réglages ou `narcisse backup` / `narcisse restore`),
  avec chiffrement par phrase de passe si tu veux ; une restauration garde d’abord tes données du
  moment.

## 0.1.0 (2026-10-27)

La première version utilisable : Narcisse cherche tes traces sur de vraies sources, les relie dans
un graphe, dit à quel point chacune est à toi et t’expose, ce que tu peux en faire, et suit tes
demandes jusqu’à ce que la trace disparaisse. S’installe avec `uv tool install` (voir le README).

- Les sources :
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
- Les fuites de données où figure un email (XposedOrNot) : quand, quelles données, et si les mots
  de passe étaient lisibles.
- Un mot de passe a-t-il fuité ? Vérification par Pwned Passwords, sans qu’il quitte la page.
- Les registres d’entreprises : les entreprises que tu diriges ou à ton nom (avec ce que le
  registre publie : mois et année de naissance, siège), et pour une entreprise ses dirigeants, son
  siège et ses annonces au BODACC.
- Les numéros de téléphone : une seule trace quelle que soit leur écriture (« 01… » ou « +33 1… »),
  et ce qu’un numéro dit de lui-même (mobile ou fixe, pays, opérateur d’origine), sans rien
  demander à personne.
- Ce que gardent les archives du web (Wayback Machine) : les pages archivées de ton site, dont un
  CV, une page contact ou des documents supprimés depuis, et depuis quand un profil est archivé.
- La recherche assistée : pour chaque élément, les recherches qui valent la peine sur Google, Bing,
  DuckDuckGo et Qwant, ouvertes dans ton navigateur (Narcisse n’interroge jamais un moteur) ; une
  page trouvée ainsi se colle en retour et rejoint tes traces.
- La recherche web pendant les scans, par ta propre instance SearXNG : `narcisse searxng`
  l’installe et la lance avec Docker, sur ta machine seulement. Arrêtée avec l’ordinateur, elle
  se relance d’un clic (fenêtre du scan, Réglages), ou toute seule avec Narcisse si tu le
  choisis.
- Épinglée à la barre des tâches, la fenêtre de Narcisse reste sous son épingle, et un lien vers
  un autre site s’ouvre dans ton navigateur, jamais dans la fenêtre de Narcisse.
- Depuis un scan, un lien bien visible ramène au profil.
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
- Deux scores par trace, expliqués règle par règle : la confiance (« est-ce toi ? ») et le risque
  (« à quel point ça t’expose ? », de faible à critique). Ton tri les met à jour, voisines
  comprises : ce qu’on n’a trouvé qu’à travers un « pas moi » est mis en doute. Dans le graphe, les
  traces les plus exposantes sont les plus grosses ; filtre et tri par risque.
- Les pistes : les traces assez sûres pour devenir des éléments, à ajouter ou écarter. Un profil
  peut laisser les scans suivre eux-mêmes les plus sûres (un ou deux sauts, 25 par scan au plus,
  jamais un « pas moi »).
- Que faire de chaque trace : supprimer le compte (page et difficulté, d’après JustDeleteMe),
  demander à un site d’effacer une page, la faire déréférencer (Google, Bing, Qwant), te retirer
  d’un courtier ou d’un annuaire d’entreprises, de la Wayback Machine, du serveur de clés,
  masquer tes coordonnées de domaine, limiter ce que publie le registre, rendre une fuite
  inoffensive. Les demandes RGPD (effacement, opposition), de suppression de compte et de
  déréférencement sont prêtes, en français ou en anglais, signées avec ton profil : tu les relis,
  les copies ou les ouvres dans ta messagerie. Narcisse n’envoie rien.
- L’onglet « À faire » suit ce que tu as fait : statut de chaque demande, relance prête au bout
  d’un mois sans réponse (rappelée une fois par jour par l’icône), vérification qui relance
  seulement les recherches concernées ; une trace qu’un scan ne retrouve plus est marquée
  disparue et sa demande close. En tête, ton exposition par niveau de risque et son évolution.
- Le type de profil compte : pour un profil pro, ton entreprise, ton domaine et le registre pèsent
  moitié moins dans le risque, et la première action proposée est de les garder.
- Une page « Sources » qui dit ce que chaque source interroge, à quel rythme et sous quelle
  licence, et une page « Réglages » (tokens GitHub et GitLab facultatifs, instances Mastodon,
  instance SearXNG, sites adultes).

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
