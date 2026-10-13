"""Whether an address is registered on Last.fm, from the live validation of its join form
("that email address is already registered"). Nothing is sent to the holder.

Light-active (opt-in): the address is handed to Last.fm. Technique from holehe (GPL-3.0).
"""

from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck, as_json

JOIN = "https://www.last.fm/join"
VALIDATE = "https://www.last.fm/join/partial/validate"
TAKEN = "already registered"


class LastFm(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="lastfm",
        title="Last.fm",
        description=(
            "Vérifie si une adresse email est inscrite sur Last.fm, via la validation en direct "
            "de son formulaire d’inscription. Rien n’est envoyé au titulaire. Source « actif "
            "léger » : l’adresse est transmise à Last.fm."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("www.last.fm",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://www.last.fm/"
    through: ClassVar[str] = "la validation de son formulaire d’inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(JOIN)
        token = page.cookies.get("csrftoken")
        if not token:
            return None
        response = await ctx.http.request(
            "POST",
            VALIDATE,
            data={"csrfmiddlewaretoken": token, "userName": "", "email": email},
            headers={"Accept": "*/*", "Referer": JOIN, "X-Requested-With": "XMLHttpRequest"},
        )
        body = as_json(response)
        if not isinstance(body, dict) or "email" not in body:
            return None
        field = body["email"] if isinstance(body["email"], dict) else {}
        errors = field.get("error_messages") or []
        # Any other error ("enter an email") or a valid field means the address is free.
        return any(TAKEN in str(message).lower() for message in errors)
