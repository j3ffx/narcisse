"""Whether an address is registered on Pinterest, from the "email exists" resource its sign-up
form calls. Nothing is sent to the holder.

Light-active (opt-in): the address is handed to Pinterest. Technique from holehe (GPL-3.0).
"""

import json
from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck, as_json

RESOURCE = "https://www.pinterest.com/_ngjs/resource/EmailExistsResource/get/"


class Pinterest(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="pinterest",
        title="Pinterest",
        description=(
            "Vérifie si une adresse email a un compte Pinterest, via le contrôle d’existence de "
            "son formulaire d’inscription. Rien n’est envoyé au titulaire. Source « actif léger "
            "» : l’adresse est transmise à Pinterest."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("www.pinterest.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://www.pinterest.com/"
    through: ClassVar[str] = "le contrôle d’existence de son inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        query = json.dumps({"options": {"email": email}, "context": {}})
        response = await ctx.http.get(RESOURCE, params={"source_url": "/", "data": query})
        body = as_json(response)
        if not isinstance(body, dict):
            return None
        try:
            data = body["resource_response"]["data"]
        except (KeyError, TypeError):
            return None
        # A validation-error object (a field problem) means Pinterest wouldn't tell us.
        if "source_field" in str(data):
            return None
        return bool(data)
