"""Whether an address already has a GitHub account, from the e-mail check its sign-up form runs
(it rejects an address that is already registered). This complements the passive GitHub module,
which finds a profile or the addresses commits carry; here only the address is tested, and nothing
is sent to the holder.

Light-active (opt-in): the address is handed to GitHub. Technique from holehe (GPL-3.0).
"""

import re
from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck

SIGNUP = "https://github.com/signup"
CHECK = "https://github.com/signup_check/email"
TOKEN = re.compile(
    r'<auto-check src="/signup_check/email[\s\S]*?name="authenticity_token"[\s\S]*?value="([^"]+)"'
)
FALLBACK = re.compile(r'name="authenticity_token" value="([^"]+)"')


class GitHubSignup(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="github_signup",
        title="GitHub (inscription)",
        description=(
            "Vérifie si une adresse email a un compte GitHub, via le contrôle d’email de son "
            "formulaire d’inscription (en plus du module GitHub passif, qui cherche un profil ou "
            "les emails des commits). Rien n’est envoyé au titulaire. Source « actif léger » : "
            "l’adresse est transmise à GitHub."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("github.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://github.com/"
    through: ClassVar[str] = "le contrôle d’email de son inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        page = await ctx.http.get(SIGNUP)
        match = TOKEN.search(page.text) or FALLBACK.search(page.text)
        if not match:
            return None
        response = await ctx.http.request(
            "POST", CHECK, data={"value": email, "authenticity_token": match.group(1)}
        )
        if "did something unexpected" in response.text.lower():
            return None
        if response.status_code == 422:  # the address is rejected: already registered
            return True
        if response.status_code == 200:
            return False
        return None
