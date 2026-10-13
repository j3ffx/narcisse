"""The shared base of the light-active e-mail checks: the opt-in gate and the three verdicts.

A test-only subclass stands in for a real site, so this covers the common logic without any
network and without naming a service. CI never checks a real address.
"""

from typing import ClassVar

import httpx
import pytest

from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import ModuleContext, ModuleMeta, RateLimit
from narcisse.modules._active import EmailCheck
from narcisse.preferences import Preferences
from tests.module_context import FakeContext, run, target


class FakeCheck(EmailCheck):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="example_check",
        title="Example",
        description="Teste si une adresse est inscrite sur example.org.",
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT}),
        intrusion=IntrusionLevel.LIGHT_ACTIVE,
        hosts=("example.org",),
        rate_limit=RateLimit(requests=1, per_seconds=3),
    )
    account_url: ClassVar[str] = "https://example.org/"
    through: ClassVar[str] = "son formulaire de mot de passe oublié"

    verdict: bool | None = None

    async def check(self, ctx: ModuleContext, email: str) -> bool | None:
        return self.verdict


def test_a_light_active_module_is_off_until_turned_on() -> None:
    module = FakeCheck()
    assert module.unavailable(Preferences()) == "light_active_off"
    assert module.unavailable(Preferences(enabled_light_active=("other",))) == "light_active_off"
    assert module.unavailable(Preferences(enabled_light_active=("example_check",))) is None


@pytest.mark.parametrize(
    ("verdict", "kinds", "note"),
    [
        (True, [(EntityKind.ACCOUNT, "registered_on", "https://example.org/")], {"found": 1}),
        (False, [], {"checked": 1}),
        (None, [], {"uncertain": 1}),
    ],
)
async def test_run_turns_a_verdict_into_a_trace_or_a_note(
    http_client: httpx.AsyncClient,
    verdict: bool | None,
    kinds: list[tuple[EntityKind, str, str]],
    note: dict[str, int],
) -> None:
    module = FakeCheck()
    module.verdict = verdict
    ctx = FakeContext(module, http_client)
    found = await run(module, ctx, target(EntityKind.EMAIL, "jeanne@example.org"))
    assert [(f.kind, f.relation, f.value) for f in found] == kinds
    assert ctx.notes == note
    if verdict is True:
        assert found[0].confidence == 0.5
