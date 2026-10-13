"""Whether an address is registered on CodePen, from the duplicate check its sign-up form runs
("that Email is already taken"). Nothing is sent to the holder.

Light-active (opt-in): the address is handed to CodePen. Technique from holehe (GPL-3.0).
"""

import re
from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck

SIGNUP = "https://codepen.io/accounts/signup/user/free"
CHECK = "https://codepen.io/accounts/duplicate_check"
TOKEN = re.compile(r'name="csrf-token"\s+content="(.*?)"')


class CodePen(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="codepen",
        title="CodePen",
        description=(
            "Vérifie si une adresse email a un compte CodePen, via le contrôle de doublon de son "
            "formulaire d’inscription. Rien n’est envoyé au titulaire. Source « actif léger » : "
            "l’adresse est transmise à CodePen."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("codepen.io",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://codepen.io/"
    through: ClassVar[str] = "le contrôle de doublon de son inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(SIGNUP)
        match = TOKEN.search(page.text)
        if not match:
            return None
        response = await ctx.http.request(
            "POST",
            CHECK,
            data={"attribute": "email", "value": email, "context": "user"},
            headers={
                "X-CSRF-Token": match.group(1),
                "X-Requested-With": "XMLHttpRequest",
                "Referer": SIGNUP,
                "Origin": "https://codepen.io",
            },
        )
        text = response.text.lower()
        if "already taken" in text:
            return True
        if "available" in text or "that email" in text or response.status_code == 200:
            return False
        return None
