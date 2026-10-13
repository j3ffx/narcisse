"""Whether an address already has a Docker Hub account, from the validation its sign-up form
runs ("this email is already in use"). Nothing is sent to the holder.

Light-active (opt-in): the address is handed to Docker. Technique from holehe (GPL-3.0).
"""

import json
from typing import ClassVar

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck, as_json

SIGNUP = "https://hub.docker.com/v2/users/signup/"


class Docker(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="docker",
        title="Docker Hub",
        description=(
            "Vérifie si une adresse email a un compte Docker Hub, via la validation de son "
            "formulaire d’inscription. Rien n’est envoyé au titulaire. Source « actif léger » : "
            "l’adresse est transmise à Docker."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("hub.docker.com",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
        licence="Technique : holehe (GPL-3.0)",
    )
    account_url: ClassVar[str] = "https://hub.docker.com/"
    through: ClassVar[str] = "la validation de son formulaire d’inscription"

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        body = json.dumps(
            {
                "email": email,
                "password": "",
                "recaptcha_response": "",
                "redirect_value": "",
                "subscribe": True,
                "username": "",
            }
        )
        response = await ctx.http.request(
            "POST",
            SIGNUP,
            content=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Referer": "https://hub.docker.com/signup",
                "Origin": "https://hub.docker.com",
            },
        )
        if "already in use" in response.text.lower():
            return True
        # A well-formed error about the other empty fields means the address is free; an HTML
        # anti-bot page (no JSON) means we couldn't tell.
        if as_json(response) is not None:
            return False
        return None
