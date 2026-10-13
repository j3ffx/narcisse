"""Whether an address is known to RocketReach, a contact-data broker, from the e-mail check its
sign-up form calls. Knowing one is listed by a broker is worth a remediation. Nothing is sent to
the holder.

Light-active (opt-in): the address is handed to RocketReach. Technique from holehe (GPL-3.0).
"""

import re
from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck, as_json

SIGNUP = "https://rocketreach.co/signup"
VALIDATE = "https://rocketreach.co/v1/validateEmail"
TOKEN = re.compile(r'name="csrfmiddlewaretoken" value="(.*?)"')


class RocketReach(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="rocketreach",
        title="RocketReach (courtier en données)",
        description=(
            "Vérifie si une adresse email est connue de RocketReach, un courtier en données de "
            "contact, via le contrôle d’email de son inscription. Figurer chez un courtier mérite "
            "souvent une demande de retrait. Source « actif léger » : l’adresse lui est transmise."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("rocketreach.co",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://rocketreach.co/"
    through: ClassVar[str] = "le contrôle d’email de son inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(SIGNUP)
        match = TOKEN.search(page.text)
        headers = {"Accept": "application/json, text/plain, */*", "Referer": SIGNUP}
        if match:
            headers["x-csrftoken"] = match.group(1)
        response = await ctx.http.get(VALIDATE, params={"email_address": email}, headers=headers)
        body = as_json(response)
        found = body.get("found") if isinstance(body, dict) else None
        return found if isinstance(found, bool) else None
