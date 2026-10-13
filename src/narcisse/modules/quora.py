"""Whether an address is registered on Quora, from the live validation of its sign-up form
(it answers that an account already uses the address). Nothing is sent to the holder.

Light-active (opt-in): the address is handed to Quora. Technique from holehe (GPL-3.0).
"""

from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck

HOME = "https://fr.quora.com"
CALL = "https://fr.quora.com/webnode2/server_call_POST"
FORMKEY = 'formkey": "'
# Quora answers the validation with this phrase when an account already uses the address.
TAKEN = "un compte a"


class Quora(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="quora",
        title="Quora",
        description=(
            "Vérifie si une adresse email a un compte Quora, via la validation en direct de son "
            "formulaire d’inscription. Rien n’est envoyé au titulaire. Source « actif léger » : "
            "l’adresse est transmise à Quora."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("fr.quora.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://www.quora.com/"
    through: ClassVar[str] = "la validation de son formulaire d’inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(HOME)
        if FORMKEY not in page.text:
            return None
        formkey = page.text.split(FORMKEY, 1)[1].split('"', 1)[0]
        data = {
            "json": '{"args":[],"kwargs":{"value":"' + email + '"}}',
            "formkey": formkey,
            "__method": "validate",
        }
        response = await ctx.http.request(
            "POST",
            CALL,
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest", "Origin": HOME, "Referer": HOME + "/"},
        )
        if response.status_code != 200:
            return None
        return TAKEN in response.text.lower()
