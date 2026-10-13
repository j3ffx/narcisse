"""The known data breaches an e-mail address appears in, from XposedOrNot (free for personal,
low-volume use; its data is credited and never redistributed).

Unlike Gravatar or Pwned Passwords, the address itself is sent: XposedOrNot looks it up as such.
Free tier: 2 requests a second, 25 an hour, 100 a day per address.
"""

from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import quote

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleMeta,
    RateLimit,
    SourceModule,
    SourceUnavailable,
    Target,
)

API = "https://api.xposedornot.com/v1/breach-analytics"
PAGE = "https://xposedornot.com/breach/"

PASSWORDS = {
    "plaintext": "en clair",
    "easytocrack": "faciles à retrouver",
    "hardtocrack": "difficiles à retrouver",
    "unknown": "dont on ne sait pas s’ils étaient protégés",
}
# The kinds of data XposedOrNot lists, as the user reads them.
DATA = {
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
    "marital statuses": "situations familiales",
    "education levels": "niveaux d’études",
    "income levels": "revenus",
    "credit cards": "cartes bancaires",
    "partial credit card data": "données partielles de cartes bancaires",
    "bank account numbers": "numéros de compte bancaire",
    "government issued ids": "pièces d’identité",
    "passport numbers": "numéros de passeport",
    "security questions and answers": "questions de sécurité",
    "purchases": "achats",
    "website activity": "activité sur le site",
    "device information": "informations sur les appareils",
    "salutations": "civilités",
    "avatars": "photos de profil",
    "profile photos": "photos de profil",
    "auth tokens": "jetons de connexion",
    "titles": "titres",
    "vehicle registration numbers": "immatriculations",
    "licence plates": "immatriculations",
    "browser user agents": "navigateurs utilisés",
    "financial transactions": "transactions financières",
    "account balances": "soldes de comptes",
    "credit card details": "cartes bancaires",
    "government ids": "pièces d’identité",
    "partial government issued ids": "pièces d’identité partielles",
    "social security numbers": "numéros de sécurité sociale",
    "private messages": "messages privés",
    "instant messenger identities": "identifiants de messageries",
}


def exposed(data: str) -> list[str]:
    return [
        DATA.get(item.strip().lower(), item.strip()) for item in data.split(";") if item.strip()
    ]


def breaches(answer: Any) -> list[dict[str, Any]]:
    """The breaches of an answer; [] when the address is in none (XposedOrNot then answers with
    empty fields rather than an error)."""
    if not isinstance(answer, dict):
        return []
    exposed_breaches = answer.get("ExposedBreaches") or {}
    details = (
        exposed_breaches.get("breaches_details") if isinstance(exposed_breaches, dict) else None
    )
    return [b for b in details or [] if isinstance(b, dict) and b.get("breach")]


class XposedOrNot(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="xposedornot",
        title="Fuites de données (XposedOrNot)",
        description=(
            "Les fuites de données connues où figure un email : quand, quelles données (mots de "
            "passe, adresses, dates de naissance…) et si les mots de passe étaient lisibles. "
            "L’adresse est envoyée à XposedOrNot, service gratuit pour un usage personnel. "
            "Données : XposedOrNot."
        ),
        category="leaks",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.LEAK}),
        hosts=("api.xposedornot.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        max_parallel_runs=1,
        licence="Données XposedOrNot : à créditer, sans redistribution",
        data_source="https://xposedornot.com/api_doc",
    )

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        response = await ctx.http.get(API, params={"email": target.normalized})
        if response.status_code == 404:
            await ctx.progress(1, 1, {"breaches": 0})
            return
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="api.xposedornot.com", status=response.status_code
            )
        try:
            found = breaches(response.json())
        except ValueError as exc:
            raise SourceUnavailable("source_unavailable", host="api.xposedornot.com") from exc
        for breach in found:
            name = str(breach["breach"])
            data = exposed(str(breach.get("xposed_data") or ""))
            risk = str(breach.get("password_risk") or "unknown")
            when = str(breach.get("xposed_date") or "").strip()
            site = str(breach.get("domain") or "").strip()
            excerpt = (
                f"Fuite {f'de {site} ' if site else ''}{f'en {when} ' if when else ''}: "
                f"{', '.join(data) or 'données non précisées'}"
            )
            if "mots de passe" in data:
                excerpt += f" ; mots de passe {PASSWORDS.get(risk, PASSWORDS['unknown'])}"
            yield Finding(
                kind=EntityKind.LEAK,
                value=name,
                relation="exposed_in",
                confidence=0.95,  # the exact address
                url=f"{PAGE}{quote(name)}",
                excerpt=f"{excerpt}. Données : XposedOrNot.",
                attributes={
                    k: v
                    for k, v in {
                        "date": when,
                        "site": site,
                        "data": data,
                        "password_risk": risk,
                        "records": breach.get("xposed_records"),
                        "industry": breach.get("industry"),
                    }.items()
                    if v
                },
            )
        await ctx.progress(1, 1, {"breaches": len(found)})
