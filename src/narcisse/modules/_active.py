"""Light-active e-mail checks: ask a service whether an address is registered with it, by sending
its public password-reset or sign-up pre-check endpoint a single lookup — never logging in, never
creating an account, never solving a captcha, with Narcisse's honest User-Agent and the per-domain
rate limit.

This reimplements the technique of holehe (GPL-3.0) for a small, curated set of services that
answer *silently*: they tell a known address apart from an unknown one without e-mailing the
account holder and without a captcha. Each such module is off until the user turns it on by name in
the settings (`Preferences.enabled_light_active`); the settings page explains each one first.

A check has three outcomes: registered (a trace), not registered (nothing), or "couldn't tell" (an
anti-bot page, an unexpected answer, a moved endpoint) — never a false yes.
"""

from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, ClassVar

import httpx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import Finding, ModuleContext, SourceModule, Target

if TYPE_CHECKING:
    from narcisse.preferences import Preferences


def as_json(response: httpx.Response) -> Any:
    """The response's JSON, or None when it isn't JSON (an anti-bot HTML page, an empty body): the
    caller then reports "couldn't tell" rather than guessing."""
    try:
        return response.json()
    except ValueError:
        return None


class EmailCheck(SourceModule):
    """A light-active check of whether one e-mail address is registered on one service.

    Subclasses give the `meta` (with `intrusion=IntrusionLevel.LIGHT_ACTIVE`, `accepts={EMAIL}`,
    `produces={ACCOUNT}` and the host(s) it contacts) and implement `check`.
    """

    # The account's canonical address on the service, used as the trace's value and link.
    account_url: ClassVar[str]
    # How it is read, for the trace's excerpt, e.g. "son formulaire de mot de passe oublié".
    through: ClassVar[str]
    # How sure "registered" means it is really this person: an address is strong but not proof.
    confidence: ClassVar[float] = 0.5

    def unavailable(self, preferences: "Preferences") -> str | None:
        """Off until the user turns this exact module on in the settings."""
        if self.meta.name not in preferences.enabled_light_active:
            return "light_active_off"
        return None

    @abstractmethod
    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        """True if the address is registered, False if not, None if it couldn't tell.

        May raise a `ModuleError` (rate limit, transient error, source unavailable); the engine
        handles those. Anything that is merely unexpected should return None, not a false True.
        """

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        verdict = await self.check(ctx, target.normalized)
        if verdict is True:
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=self.account_url,
                relation="registered_on",
                confidence=self.confidence,
                url=self.account_url,
                excerpt=(
                    f"{target.value} est inscrit sur {self.meta.title} "
                    f"(vu via {self.through}, sans rien envoyer au titulaire)."
                ),
            )
            await ctx.progress(1, 1, {"found": 1})
        elif verdict is False:
            await ctx.progress(1, 1, {"checked": 1})
        else:
            await ctx.progress(1, 1, {"uncertain": 1})
