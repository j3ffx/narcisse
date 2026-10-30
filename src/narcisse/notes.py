"""What a proof says, in both languages.

A source doesn't write its proof as a sentence: it gives a code and the facts (`note("github_name",
login="octocat")`), and the sentence is written when it is read, in the reader's language. A fact
may itself be a note (where something was read), or text in both languages ({"fr": …, "en": …},
a country's name, say). Text read on a page (a bio, a title) stays apart, in its own language
(`Finding.excerpt`). Proofs stored before notes existed keep their French sentence.
"""

from collections.abc import Callable, Mapping
from typing import Any

from narcisse.i18n import Lang

Note = dict[str, Any]  # {"code": str, "params": {…}}
Render = Callable[[Mapping[str, Any]], str]


def note(code: str, **params: Any) -> Note:
    if code not in NOTES:
        raise KeyError(f"no text for the note {code!r}")
    return {"code": code, "params": {k: v for k, v in params.items() if v is not None}}


def render(value: Note | None, lang: Lang) -> str | None:
    """The note as a sentence in this language (None for no note, or one we can't read)."""
    if not isinstance(value, dict) or value.get("code") not in NOTES:
        return None
    params = {k: _param(v, lang) for k, v in (value.get("params") or {}).items()}
    try:
        return NOTES[value["code"]][lang](params)
    except (KeyError, TypeError, ValueError):
        return None


def _param(value: Any, lang: Lang) -> Any:
    if isinstance(value, dict) and "code" in value:
        return render(value, lang) or ""
    if isinstance(value, dict) and set(value) <= {"fr", "en"}:
        return value.get(lang) or value.get("fr") or ""
    return value


def text(value: Note | None, excerpt: str | None, lang: Lang) -> str | None:
    """A proof as read: its note's sentence, then the text read on the page."""
    parts = [part for part in (render(value, lang), excerpt) if part]
    return " ".join(parts) or None


def de(name: str) -> str:
    """« de » before a name, elided before a vowel: « d’Adobe », « de Google »."""
    return f"d’{name}" if name[:1].lower() in "aeiouyéè" else f"de {name}"


def s(count: int) -> str:
    return "s" if count > 1 else ""


def _between(p: Mapping[str, Any], fr: bool) -> str:
    if p.get("first") and p.get("last"):
        return f", du {p['first']} au {p['last']}" if fr else f", from {p['first']} to {p['last']}"
    return ""


def _fr_company(p: Mapping[str, Any]) -> str:
    state = "en activité" if p.get("active") else "fermée"
    created = f", créée le {p['created']}" if p.get("created") else ""
    office = f" Siège : {p['office']}." if p.get("office") else ""
    return f"{state}{created}).{office}"


def _en_company(p: Mapping[str, Any]) -> str:
    state = "active" if p.get("active") else "closed"
    created = f", created on {p['created']}" if p.get("created") else ""
    office = f" Registered office: {p['office']}." if p.get("office") else ""
    return f"{state}{created}).{office}"


LEAK_DATA = {
    "email addresses": "adresses email",
    "names": "noms",
    "usernames": "pseudos",
    "passwords": "mots de passe",
    "phone numbers": "numéros de téléphone",
    "physical addresses": "adresses postales",
    "dates of birth": "dates de naissance",
    "genders": "genres",
    "ages": "âges",
    "ip addresses": "adresses IP",
    "geographic locations": "localisations",
    "job titles": "postes",
    "employers": "employeurs",
    "social media profiles": "profils de réseaux sociaux",
    "spoken languages": "langues",
    "nationalities": "nationalités",
}
LEAK_PASSWORDS = {
    "plaintext": ("en clair", "in plain text"),
    "easytocrack": ("faciles à retrouver", "easy to crack"),
    "hardtocrack": ("difficiles à retrouver", "hard to crack"),
    "unknown": ("dont on ne sait pas s’ils étaient protégés", "of unknown protection"),
}
PHONE_TYPES = {
    "mobile": ("Mobile", "Mobile"),
    "fixed_line": ("Fixe", "Landline"),
    "fixed_or_mobile": ("Fixe ou mobile", "Landline or mobile"),
    "voip": ("Téléphonie par internet", "Internet telephony"),
    "toll_free": ("Numéro gratuit", "Toll-free number"),
    "premium_rate": ("Numéro surtaxé", "Premium-rate number"),
    "shared_cost": ("Numéro à coût partagé", "Shared-cost number"),
    "personal_number": ("Numéro personnel", "Personal number"),
    "uan": ("Numéro d’entreprise", "Company number"),
    "voicemail": ("Messagerie vocale", "Voicemail"),
    "pager": ("Bipeur", "Pager"),
    "unknown": ("Numéro", "Number"),
}
REGISTRY_ROLES = {
    "registrant": ("titulaire", "holder"),
    "administrative": ("contact administratif", "administrative contact"),
    "technical": ("contact technique", "technical contact"),
}
DNS_ROLES = {
    "mail": (
        lambda p: f"Les emails {de(p['domain'])} sont reçus par {p['service']}",
        lambda p: f"Mail for {p['domain']} is received by {p['service']}",
    ),
    "dns": (
        lambda p: f"Le DNS {de(p['domain'])} est servi par {p['service']}",
        lambda p: f"The DNS of {p['domain']} is served by {p['service']}",
    ),
    "sending": (
        lambda p: f"{p['service']} peut envoyer des emails au nom {de(p['domain'])}",
        lambda p: f"{p['service']} may send mail on behalf of {p['domain']}",
    ),
    "verified": (
        lambda p: f"{p['domain']} a été vérifié auprès {de(p['service'])}",
        lambda p: f"{p['domain']} was verified with {p['service']}",
    ),
    "hosting": (
        lambda p: f"Le site {de(p['domain'])} est hébergé chez {p['service']}",
        lambda p: f"The site of {p['domain']} is hosted by {p['service']}",
    ),
}


def _and(items: list[str], word: str) -> str:
    return f" {word} ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else items[0]


def _fr_registration(p: Mapping[str, Any]) -> str:
    intro = f"{p['domain']} (domaine parent de {p['child']})" if p.get("child") else p["domain"]
    dates = (f" le {p['created']}" if p.get("created") else "") + (
        f", expire le {p['expires']}" if p.get("expires") else ""
    )
    shown = {"shown": "publiées", "hidden": "masquées"}.get(p.get("contacts", ""), "absentes")
    return (
        f"{intro} est enregistré chez {p['registrar']}{dates}. Coordonnées du titulaire : {shown}."
    )


def _en_registration(p: Mapping[str, Any]) -> str:
    intro = f"{p['domain']} (parent domain of {p['child']})" if p.get("child") else p["domain"]
    dates = (f" on {p['created']}" if p.get("created") else "") + (
        f", expiring on {p['expires']}" if p.get("expires") else ""
    )
    shown = {"shown": "published", "hidden": "hidden"}.get(p.get("contacts", ""), "absent")
    return f"{intro} is registered with {p['registrar']}{dates}. Holder's contact details: {shown}."


def _roles(p: Mapping[str, Any], index: int, word: str) -> str:
    return _and([REGISTRY_ROLES[r][index] for r in p["roles"]], word)


def _passwords(p: Mapping[str, Any]) -> bool:
    return any(str(d).lower() == "passwords" for d in p.get("data", []))


def _fr_leak(p: Mapping[str, Any]) -> str:
    data = [LEAK_DATA.get(d.lower(), d) for d in p.get("data", [])]
    site = f"de {p['site']} " if p.get("site") else ""
    when = f"en {p['date']} " if p.get("date") else ""
    text = f"Fuite {site}{when}: {', '.join(data) or 'données non précisées'}"
    if _passwords(p):
        risk = LEAK_PASSWORDS.get(p.get("risk", ""), LEAK_PASSWORDS["unknown"])[0]
        text += f" ; mots de passe {risk}"
    return f"{text}. Données : XposedOrNot."


def _en_leak(p: Mapping[str, Any]) -> str:
    site = f"of {p['site']} " if p.get("site") else ""
    when = f"in {p['date']} " if p.get("date") else ""
    text = f"Breach {site}{when}: {', '.join(p.get('data', [])) or 'data not specified'}"
    if _passwords(p):
        risk = LEAK_PASSWORDS.get(p.get("risk", ""), LEAK_PASSWORDS["unknown"])[1]
        text += f"; passwords {risk}"
    return f"{text}. Data: XposedOrNot."


def _certificates(p: Mapping[str, Any], fr: bool) -> str:
    count = int(p["count"])
    valid = p.get("source") != "crt.sh"
    if fr:
        what = "Nom vu" if p["what"] == "name" else "Adresse inscrite"
        valid_text = f" encore valide{s(count)}" if valid else ""
        span = _between(p, True)
        return f"{what} dans {count} certificat{s(count)}{valid_text}{span} ({p['source']})."
    what = "Name seen" if p["what"] == "name" else "Address written"
    valid_text = " still valid" if valid else ""
    plural = "s" if count > 1 else ""
    return f"{what} in {count}{valid_text} certificate{plural}{_between(p, False)} ({p['source']})."


def _phone(p: Mapping[str, Any], fr: bool) -> str:
    index = 0 if fr else 1
    parts = [PHONE_TYPES.get(p.get("type", ""), PHONE_TYPES["unknown"])[index]]
    parts += [p[k] for k in ("country", "region") if p.get(k)]
    sentence = ", ".join(parts) + "."
    if p.get("carrier"):
        sentence += (
            f" Opérateur d’origine : {p['carrier']} (le numéro a pu changer d’opérateur depuis)."
            if fr
            else f" Original carrier: {p['carrier']} (the number may have moved since)."
        )
    return sentence


def both(fr: Render, en: Render) -> dict[Lang, Render]:
    return {"fr": fr, "en": en}


NOTES: dict[str, dict[Lang, Render]] = {
    # Where something was read (a fact of another note).
    "in_bluesky_description": both(
        lambda p: f"dans la description du compte Bluesky « {p['handle']} »",
        lambda p: f"in the description of the Bluesky account “{p['handle']}”",
    ),
    "in_fediverse_bio": both(
        lambda p: f"dans la bio de « {p['handle']} »",
        lambda p: f"in the bio of “{p['handle']}”",
    ),
    "in_fediverse_field": both(
        lambda p: f"dans le profil de « {p['handle']} » (champ « {p['label']} »)",
        lambda p: f"in the profile of “{p['handle']}” (field “{p['label']}”)",
    ),
    "in_github_bio": both(
        lambda p: f"dans la bio du profil GitHub « {p['login']} »",
        lambda p: f"in the bio of the GitHub profile “{p['login']}”",
    ),
    "on_gitlab_profile": both(
        lambda p: f"sur le profil GitLab « {p['username']} » ({p['host']})",
        lambda p: f"on the GitLab profile “{p['username']}” ({p['host']})",
    ),
    "in_hackernews_about": both(
        lambda p: f"dans la présentation du compte Hacker News « {p['username']} »",
        lambda p: f"in the about of the Hacker News account “{p['username']}”",
    ),
    "in_keybase_bio": both(
        lambda p: f"dans la bio du compte Keybase « {p['username']} »",
        lambda p: f"in the bio of the Keybase account “{p['username']}”",
    ),
    "on_stackoverflow_profile": both(
        lambda p: f"sur le profil Stack Overflow « {p['name']} »",
        lambda p: f"on the Stack Overflow profile “{p['name']}”",
    ),
    # Read in a profile's text
    "link_given": both(
        lambda p: f"Lien indiqué {p['where']}.", lambda p: f"Link given {p['where']}."
    ),
    "email_given": both(
        lambda p: f"Adresse indiquée {p['where']}.", lambda p: f"Address given {p['where']}."
    ),
    "name_shown": both(
        lambda p: f"Nom affiché {p['where']}.", lambda p: f"Name shown {p['where']}."
    ),
    "public_email": both(
        lambda p: f"Email public {p['where']}.", lambda p: f"Public email {p['where']}."
    ),
    "site_given": both(
        lambda p: f"Site indiqué {p['where']}.", lambda p: f"Website given {p['where']}."
    ),
    "account_given": both(
        lambda p: f"Compte {p['site']} indiqué {p['where']}.",
        lambda p: f"{p['site']} account given {p['where']}.",
    ),
    # Bluesky
    "bluesky_account": both(
        lambda p: f"Compte Bluesky « {p['handle']} » ({p.get('posts', 0)} publications).",
        lambda p: f"Bluesky account “{p['handle']}” ({p.get('posts', 0)} posts).",
    ),
    "bluesky_domain_handle": both(
        lambda p: (
            f"Le compte Bluesky utilise le domaine « {p['handle']} » comme pseudo : "
            "Bluesky a vérifié que son titulaire contrôle ce domaine."
        ),
        lambda p: (
            f"The Bluesky account uses the domain “{p['handle']}” as its handle: "
            "Bluesky checked that its holder controls the domain."
        ),
    ),
    "bluesky_name": both(
        lambda p: f"Nom affiché sur le compte Bluesky « {p['handle']} ».",
        lambda p: f"Name shown on the Bluesky account “{p['handle']}”.",
    ),
    # Certificates
    "certificates": both(lambda p: _certificates(p, True), lambda p: _certificates(p, False)),
    # Companies (French registers)
    "company_officer": both(
        lambda p: (
            f"{p['who']}, {str(p.get('role') or 'dirigeant').lower()}"
            f"{', né·e en ' + p['born'] if p.get('born') else ''}, de {p['name']} ("
            + _fr_company(p)
        ),
        lambda p: (
            f"{p['who']}, {str(p.get('role') or 'officer').lower()}"
            f"{', born in ' + p['born'] if p.get('born') else ''}, of {p['name']} ("
            + _en_company(p)
        ),
    ),
    "sole_trader": both(
        lambda p: f"Entreprise individuelle {p['name']} (" + _fr_company(p),
        lambda p: f"Sole proprietorship {p['name']} (" + _en_company(p),
    ),
    "registered_office": both(
        lambda p: f"Siège de {p['name']}, publié au registre.",
        lambda p: f"Registered office of {p['name']}, published in the register.",
    ),
    "company_in_register": both(
        lambda p: f"{p['name']} au registre, SIREN {p['siren']}.",
        lambda p: f"{p['name']} in the register, SIREN {p['siren']}.",
    ),
    "officer": both(
        lambda p: (
            f"{p['who']}, {str(p.get('role') or 'dirigeant').lower()} de {p['name']}"
            f"{', né·e en ' + p['born'] if p.get('born') else ''}."
        ),
        lambda p: (
            f"{p['who']}, {str(p.get('role') or 'officer').lower()} of {p['name']}"
            f"{', born in ' + p['born'] if p.get('born') else ''}."
        ),
    ),
    "legal_notice": both(
        lambda p: (
            f"Annonce au BODACC{' du ' + p['date'] if p.get('date') else ''} : "
            f"{str(p.get('what') or 'annonce').lower()} "
            f"({p['name']}{', ' + str(p['court']).lower() if p.get('court') else ''})."
        ),
        lambda p: (
            f"Notice in the BODACC{' of ' + p['date'] if p.get('date') else ''}: "
            f"{str(p.get('what') or 'notice').lower()} "
            f"({p['name']}{', ' + str(p['court']).lower() if p.get('court') else ''})."
        ),
    ),
    # Demo mode
    "demo_result": both(
        lambda p: f"Résultat fictif du module de démonstration, à partir de « {p['value']} ».",
        lambda p: f"Fictitious result of the demo module, from “{p['value']}”.",
    ),
    "demo_account": both(
        lambda p: (
            f"Résultat fictif du module de démonstration, à partir de « {p['value']} ». "
            f"Compte « {p['handle']} » sur {p['site']} (fictif)."
        ),
        lambda p: (
            f"Fictitious result of the demo module, from “{p['value']}”. "
            f"Account “{p['handle']}” on {p['site']} (fictitious)."
        ),
    ),
    "demo_email": both(
        lambda p: (
            f"Résultat fictif du module de démonstration, à partir de « {p['value']} ». "
            "Adresse affichée sur ce compte (fictif)."
        ),
        lambda p: (
            f"Fictitious result of the demo module, from “{p['value']}”. "
            "Address shown on this account (fictitious)."
        ),
    ),
    "demo_graph": both(
        lambda p: "Trace fictive, générée pour la démonstration du graphe.",
        lambda p: "Fictitious trace, made up for the graph demo.",
    ),
    # DNS
    "dns_service": both(
        lambda p: DNS_ROLES[p["role"]][0](p) + f" ({p['record']}).",
        lambda p: DNS_ROLES[p["role"]][1](p) + f" ({p['record']}).",
    ),
    "dmarc_reports": both(
        lambda p: f"Adresse qui reçoit les rapports DMARC {de(p['domain'])}.",
        lambda p: f"Address receiving the DMARC reports of {p['domain']}.",
    ),
    "dns_contact": both(
        lambda p: f"Adresse du responsable de la zone DNS {de(p['domain'])} (SOA).",
        lambda p: f"Address of the person in charge of the DNS zone of {p['domain']} (SOA).",
    ),
    # Fediverse
    "fediverse_account": both(
        lambda p: f"Compte « {p['handle']} » sur l’instance {p['host']}.",
        lambda p: f"Account “{p['handle']}” on the instance {p['host']}.",
    ),
    "fediverse_name": both(
        lambda p: f"Nom affiché sur le compte « {p['handle']} ».",
        lambda p: f"Name shown on the account “{p['handle']}”.",
    ),
    "fediverse_moved": both(
        lambda p: f"Le compte « {p['handle']} » a déménagé vers ce compte.",
        lambda p: f"The account “{p['handle']}” moved to this account.",
    ),
    "fediverse_verified_link": both(
        lambda p: (
            f"Lien vérifié par Mastodon dans le profil de « {p['handle']} » "
            f"(champ « {p['label']} ») : la page renvoie vers le compte."
        ),
        lambda p: (
            f"Link verified by Mastodon in the profile of “{p['handle']}” "
            f"(field “{p['label']}”): the page links back to the account."
        ),
    ),
    # GitHub
    "github_profile": both(
        lambda p: f"Profil GitHub « {p['login']} » ({p.get('repos', 0)} dépôts publics).",
        lambda p: f"GitHub profile “{p['login']}” ({p.get('repos', 0)} public repositories).",
    ),
    "github_name": both(
        lambda p: f"Nom affiché sur le profil GitHub « {p['login']} ».",
        lambda p: f"Name shown on the GitHub profile “{p['login']}”.",
    ),
    "github_email": both(
        lambda p: f"Email public du profil GitHub « {p['login']} ».",
        lambda p: f"Public email of the GitHub profile “{p['login']}”.",
    ),
    "github_site": both(
        lambda p: f"Site indiqué sur le profil GitHub « {p['login']} ».",
        lambda p: f"Website given on the GitHub profile “{p['login']}”.",
    ),
    "github_x": both(
        lambda p: f"Compte X indiqué sur le profil GitHub « {p['login']} ».",
        lambda p: f"X account given on the GitHub profile “{p['login']}”.",
    ),
    "github_commit_email": both(
        lambda p: (
            f"Adresse d’auteur des commits de « {p['login']} » dans {p['repo']} "
            f"(signés « {p.get('author', '?')} »)."
        ),
        lambda p: (
            f"Author address of commits by “{p['login']}” in {p['repo']} "
            f"(signed “{p.get('author', '?')}”)."
        ),
    ),
    "github_commits_by": both(
        lambda p: (
            f"Des commits portant cette adresse sont rattachés au compte GitHub "
            f"« {p['login']} » (par exemple dans {p.get('repo', '?')})."
        ),
        lambda p: (
            f"Commits bearing this address are linked to the GitHub account "
            f"“{p['login']}” (for example in {p.get('repo', '?')})."
        ),
    ),
    # GitLab
    "gitlab_profile": both(
        lambda p: f"Profil GitLab « {p['username']} » sur {p['host']}.",
        lambda p: f"GitLab profile “{p['username']}” on {p['host']}.",
    ),
    "gitlab_commit_email": both(
        lambda p: (
            f"Adresse d’auteur d’un commit poussé par « {p['username']} » sur {p['host']} "
            f"(signé « {p.get('author', '?')} »)."
        ),
        lambda p: (
            f"Author address of a commit pushed by “{p['username']}” on {p['host']} "
            f"(signed “{p.get('author', '?')}”)."
        ),
    ),
    # Gravatar
    "gravatar_profile": both(
        lambda p: "Profil Gravatar public rattaché à cet email.",
        lambda p: "Public Gravatar profile tied to this email.",
    ),
    "gravatar_name": both(
        lambda p: "Nom affiché sur le profil Gravatar.",
        lambda p: "Name shown on the Gravatar profile.",
    ),
    "gravatar_account": both(
        lambda p: f"Compte {p['site']} vérifié, listé sur le profil Gravatar.",
        lambda p: f"Verified {p['site']} account, listed on the Gravatar profile.",
    ),
    # Hacker News
    "hackernews_account": both(
        lambda p: f"Compte Hacker News « {p['username']} » ({p.get('karma', 0)} de karma).",
        lambda p: f"Hacker News account “{p['username']}” ({p.get('karma', 0)} karma).",
    ),
    # Keybase
    "keybase_account": both(
        lambda p: f"Compte Keybase « {p['username']} ».",
        lambda p: f"Keybase account “{p['username']}”.",
    ),
    "keybase_proves_domain": both(
        lambda p: f"Le compte Keybase « {p['username']} » a prouvé contrôler ce domaine.",
        lambda p: f"The Keybase account “{p['username']}” proved it controls this domain.",
    ),
    "keybase_proves_account": both(
        lambda p: (
            f"Le compte Keybase « {p['username']} » a prouvé posséder le compte "
            f"{p['service']} « {p['value']} »."
        ),
        lambda p: (
            f"The Keybase account “{p['username']}” proved it owns the {p['service']} "
            f"account “{p['value']}”."
        ),
    ),
    "keybase_name": both(
        lambda p: f"Nom affiché sur le compte Keybase « {p['username']} ».",
        lambda p: f"Name shown on the Keybase account “{p['username']}”.",
    ),
    "keybase_domain": both(
        lambda p: f"Domaine dont le compte Keybase « {p['username']} » a prouvé le contrôle.",
        lambda p: f"Domain the Keybase account “{p['username']}” proved it controls.",
    ),
    "keybase_linked": both(
        lambda p: (
            f"Compte {p['service']} « {p.get('nametag', '?')} » relié au compte Keybase "
            f"« {p['username']} » par une preuve d’identité signée."
        ),
        lambda p: (
            f"{p['service']} account “{p.get('nametag', '?')}” linked to the Keybase "
            f"account “{p['username']}” by a signed identity proof."
        ),
    ),
    # PGP
    "pgp_key": both(
        lambda p: f"Une clé PGP publique est publiée pour {p['email']}.",
        lambda p: f"A public PGP key is published for {p['email']}.",
    ),
    "pgp_identity": both(
        lambda p: f"Identité portée par la clé PGP : « {p['identity']} ».",
        lambda p: f"Identity carried by the PGP key: “{p['identity']}”.",
    ),
    "pgp_other_email": both(
        lambda p: f"Autre adresse portée par la même clé PGP : « {p['identity']} ».",
        lambda p: f"Another address carried by the same PGP key: “{p['identity']}”.",
    ),
    # Phone
    "phone_unassigned": both(
        lambda p: (
            "Numéro qui n’est attribué à personne d’après le plan de numérotation "
            "(réservé, fictif ou mal saisi)."
        ),
        lambda p: (
            "Number assigned to no one according to the numbering plan "
            "(reserved, fictitious or mistyped)."
        ),
    ),
    "phone_described": both(lambda p: _phone(p, True), lambda p: _phone(p, False)),
    # Domain registration
    "registered_with": both(_fr_registration, _en_registration),
    "registry_contact": both(
        lambda p: (
            f"Publié comme {_roles(p, 0, 'et')} de "
            + (f"{p['domain']} (domaine parent de {p['child']})" if p.get("child") else p["domain"])
            + " par le registre."
        ),
        lambda p: (
            f"Published as {_roles(p, 1, 'and')} of "
            + (f"{p['domain']} (parent domain of {p['child']})" if p.get("child") else p["domain"])
            + " by the registry."
        ),
    ),
    # Stack Exchange
    "stackexchange_same_holder": both(
        lambda p: (
            f"Compte du même titulaire sur {p.get('site', '?')} "
            "(réseau Stack Exchange), relié à un compte Stack Overflow homonyme."
        ),
        lambda p: (
            f"Account of the same holder on {p.get('site', '?')} "
            "(Stack Exchange network), linked to a Stack Overflow account of the same name."
        ),
    ),
    "stackoverflow_user": both(
        lambda p: (
            f"Utilisateur Stack Overflow « {p['name']} » "
            f"({p.get('reputation', 0)} points de réputation)."
        ),
        lambda p: f"Stack Overflow user “{p['name']}” ({p.get('reputation', 0)} reputation).",
    ),
    # Wayback Machine
    "wayback_domain": both(
        lambda p: (
            f"{p['count']}{'+' if p.get('more') else ''} page{s(int(p['count']))} "
            f"{de(p['domain'])} archivée{s(int(p['count']))} par la Wayback Machine"
            f"{_between(p, True)}."
        ),
        lambda p: (
            f"{p['count']}{'+' if p.get('more') else ''} page{s(int(p['count']))} "
            f"of {p['domain']} archived by the Wayback Machine{_between(p, False)}."
        ),
    ),
    "wayback_page": both(
        lambda p: f"Page archivée le {p['date']} : {p['url']}",
        lambda p: f"Page archived on {p['date']}: {p['url']}",
    ),
    "wayback_archived": both(
        lambda p: (
            f"Archivé par la Wayback Machine, {p['months']} mois différents"
            f"{_between(p, True)} : la page reste lisible là-bas même si elle disparaît."
        ),
        lambda p: (
            f"Archived by the Wayback Machine, {p['months']} different months"
            f"{_between(p, False)}: the page stays readable there even if it disappears."
        ),
    ),
    # A domain's website
    "site_redirects": both(
        lambda p: f"Le site {de(p['domain'])} renvoie vers cette adresse.",
        lambda p: f"The website of {p['domain']} redirects to this address.",
    ),
    "site_on_publisher": both(
        lambda p: f"Page du site {de(p['domain'])} sur son éditeur.",
        lambda p: f"Page of the website of {p['domain']} about its publisher.",
    ),
    "site_profile_link": both(
        lambda p: f"Lien vers un profil, sur le site {de(p['domain'])}.",
        lambda p: f"Link to a profile, on the website of {p['domain']}.",
    ),
    "mailto_link": both(
        lambda p: "Lien mailto: de la page.", lambda p: "mailto: link on the page."
    ),
    "tel_link": both(lambda p: "Lien tel: de la page.", lambda p: "tel: link on the page."),
    # WhatsMyName
    "account_exists": both(
        lambda p: (
            f"Un compte « {p['username']} » existe sur {p['site']}"
            f"{' (site adulte)' if p.get('adult') else ''}."
        ),
        lambda p: (
            f"An account “{p['username']}” exists on {p['site']}"
            f"{' (adult site)' if p.get('adult') else ''}."
        ),
    ),
    # Leaks
    "leak": both(_fr_leak, _en_leak),
    # Added by hand
    "added_by_hand": both(lambda p: "Ajoutée par toi.", lambda p: "Added by you."),
}
