"""Whether an address is registered on SoundCloud, from the identifier check its sign-in flow
calls (it answers "in_use" or "available"). Nothing is sent to the holder.

Light-active (opt-in): the address is handed to SoundCloud. Technique from holehe (GPL-3.0).
"""

import re
from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck, as_json

PAGE = "https://soundcloud.com/"
AUTH = "https://api-auth.soundcloud.com/web-auth/identifier"
CLIENT_ID = re.compile(r'"clientId":"(\w+)"')


class SoundCloud(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="soundcloud",
        title="SoundCloud",
        description=(
            "Vérifie si une adresse email a un compte SoundCloud, via le contrôle d’identifiant de "
            "sa connexion. Rien n’est envoyé au titulaire. Source « actif léger » : l’adresse est "
            "transmise à SoundCloud."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("soundcloud.com", "api-auth.soundcloud.com"),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://soundcloud.com/"
    through: ClassVar[str] = "le contrôle d’identifiant de sa connexion"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(PAGE)
        match = CLIENT_ID.search(page.text)
        if not match:
            return None
        response = await ctx.http.get(AUTH, params={"q": email, "client_id": match.group(1)})
        body = as_json(response)
        status = body.get("status") if isinstance(body, dict) else None
        if status == "in_use":
            return True
        if status == "available":
            return False
        return None
