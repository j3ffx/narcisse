"""Whether an address is registered on Strava, from the uniqueness check its sign-up form runs
(it answers "false" for a taken address, "true" for a free one). Nothing is sent to the holder.
A Strava account can expose someone's movements, so it is worth knowing about.

Light-active (opt-in): the address is handed to Strava. Technique from holehe (GPL-3.0).
"""

from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck

REGISTER = "https://www.strava.com/register/free"
UNIQUE = "https://www.strava.com/athletes/email_unique"
META = '<meta name="csrf-token" content="'


class Strava(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="strava",
        title="Strava",
        description=(
            "Vérifie si une adresse email a un compte Strava, via le contrôle d’unicité de son "
            "formulaire d’inscription. Un compte Strava peut révéler des déplacements. Rien n’est "
            "envoyé au titulaire. Source « actif léger » : l’adresse est transmise à Strava."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("www.strava.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://www.strava.com/"
    through: ClassVar[str] = "le contrôle d’unicité de son inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(REGISTER)
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": REGISTER}
        if META in page.text:
            headers["X-CSRF-Token"] = page.text.split(META, 1)[1].split('"', 1)[0]
        response = await ctx.http.get(UNIQUE, params={"email": email}, headers=headers)
        body = response.text.strip().lower()
        if body == "false":
            return True
        if body == "true":
            return False
        return None
