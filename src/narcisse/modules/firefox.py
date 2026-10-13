"""Whether an address has a Mozilla (Firefox) account, from its public account-status API — the
one the sign-up form calls to tell a free address from a taken one. Nothing is sent to the holder.

Light-active (opt-in): the address is handed to Mozilla. Technique from holehe (GPL-3.0).
"""

from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck, as_json

API = "https://api.accounts.firefox.com/v1/account/status"


class Firefox(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="firefox",
        title="Compte Mozilla (Firefox)",
        description=(
            "Vérifie si une adresse email a un compte Mozilla (Firefox, synchronisation…), via "
            "l’API publique de son formulaire d’inscription. Rien n’est envoyé au titulaire. "
            "Source « actif léger » : l’adresse est transmise à Mozilla."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("api.accounts.firefox.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://accounts.firefox.com/"
    through: ClassVar[str] = "l’API de son formulaire d’inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        response = await ctx.http.request("POST", API, data={"email": email})
        body = as_json(response)
        exists = body.get("exists") if isinstance(body, dict) else None
        return exists if isinstance(exists, bool) else None
