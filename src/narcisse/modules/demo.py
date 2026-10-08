"""Demo module: fictitious results, with errors and rate limits on cue. Contacts nobody.

It exists to show and test what a scan looks like (live results, waits, failures, retries) without
touching the network or a real identity. Only offered in demo mode, and labelled as fake.
"""

import hashlib
import random
import re
from collections.abc import AsyncIterator
from typing import ClassVar

from narcisse.domain import SEED_KINDS, EntityKind
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleMeta,
    RateLimited,
    SourceModule,
    SourceUnavailable,
    Target,
    TransientError,
)

STEPS = 12
STEP_SECONDS = 2.5  # about 30 s per run
RATE_LIMIT_SECONDS = 8.0
HOST = "demo.example"  # shown in the fake errors; never contacted

PLATFORMS = (
    ("Forum", "https://forum.example.org/u/{h}"),
    ("Photos", "https://photos.example.net/{h}"),
    ("Code", "https://code.example.com/{h}"),
    ("Musique", "https://musique.example.org/@{h}"),
    ("Blog", "https://blog.example.net/{h}"),
    ("Petites annonces", "https://annonces.example.com/vendeur/{h}"),
)
PAGES = (
    "https://annuaire.example.org/personnes/{h}",
    "https://journal.example.net/2025/06/portrait-{h}",
    "https://association.example.com/bureau#{h}",
)


def handle_of(target: Target) -> str:
    """A plausible username derived from the target (« Jeanne Exemple » → jeanne.exemple)."""
    base = target.normalized
    if target.kind == EntityKind.EMAIL:
        base = base.split("@")[0]
    elif target.kind == EntityKind.DOMAIN:
        base = base.split(".")[0]
    elif target.kind == EntityKind.PHONE:
        base = "contact" + base[-4:]
    elif target.kind == EntityKind.ACCOUNT:
        base = base.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]+", ".", base.lower()).strip(".") or "anonyme"


def findings_for(target: Target, rng: random.Random) -> list[Finding]:
    h = handle_of(target)
    excerpt = f"Résultat fictif du module de démonstration, à partir de « {target.value} »."
    found: list[Finding] = []
    for title, url in rng.sample(PLATFORMS, k=len(PLATFORMS)):
        found.append(
            Finding(
                kind=EntityKind.ACCOUNT,
                value=url.format(h=h),
                relation="has_account",
                confidence=round(rng.uniform(0.3, 0.95), 2),
                url=url.format(h=h),
                excerpt=f"{excerpt} Compte « {h} » sur {title} (fictif).",
                content=f"{title}:{h}",
            )
        )
    for page in PAGES:
        found.append(
            Finding(
                kind=EntityKind.URL,
                value=page.format(h=h),
                relation="mentioned_on",
                confidence=round(rng.uniform(0.2, 0.8), 2),
                url=page.format(h=h),
                excerpt=excerpt,
                content=page.format(h=h),
            )
        )
    found.append(
        Finding(
            kind=EntityKind.EMAIL,
            value=f"{h}@example.com",
            relation="uses_email",
            confidence=round(rng.uniform(0.4, 0.9), 2),
            url=PAGES[0].format(h=h),
            excerpt=excerpt,
        )
    )
    found.append(
        Finding(
            kind=EntityKind.USERNAME,
            value=f"{h}{rng.randint(1, 99)}",
            relation="uses_username",
            confidence=round(rng.uniform(0.2, 0.6), 2),
            url=PLATFORMS[0][1].format(h=h),
            excerpt=excerpt,
        )
    )
    found.append(
        Finding(
            kind=EntityKind.USERNAME,
            value=f"{h.replace('.', '_')}",
            relation="uses_username",
            confidence=round(rng.uniform(0.3, 0.7), 2),
            url=PLATFORMS[1][1].format(h=h),
            excerpt=excerpt,
        )
    )
    return found[:STEPS]


class DemoModule(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="demo.fake",
        title="Module de démonstration",
        description=(
            "Produit des résultats fictifs pendant une trentaine de secondes, avec des erreurs et "
            "des limites de débit simulées. N’interroge aucun site."
        ),
        category="demo",
        accepts=SEED_KINDS,
        produces=frozenset(
            {EntityKind.ACCOUNT, EntityKind.URL, EntityKind.EMAIL, EntityKind.USERNAME}
        ),
        max_parallel_runs=8,
        demo=True,
    )

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        # Same input, same results, same delays: tests and demos can rely on it.
        seed = hashlib.sha256(f"{target.kind}:{target.normalized}".encode()).digest()
        rng = random.Random(seed)
        findings = findings_for(target, rng)
        delays = [STEP_SECONDS * rng.uniform(0.6, 1.4) for _ in range(STEPS)]
        state = dict(ctx.checkpoint or {})
        for step in range(int(state.get("step", 0)), STEPS):
            await ctx.progress(step, STEPS)
            await ctx.sleep(delays[step])
            await self._simulate_trouble(ctx, target, step, state)
            yield findings[step]
            state["step"] = step + 1
            await ctx.save_checkpoint(state)
        await ctx.progress(STEPS, STEPS)

    async def _simulate_trouble(
        self, ctx: ModuleContext, target: Target, step: int, state: dict[str, object]
    ) -> None:
        """Each kind of input shows one way a real source misbehaves, once."""
        match target.kind:
            case EntityKind.USERNAME if step == 5 and "limited" not in state:
                state.update(step=step, limited=True)
                await ctx.save_checkpoint(state)
                raise RateLimited(RATE_LIMIT_SECONDS, host=HOST)
            case EntityKind.EMAIL if step == 3 and "glitch" not in state:
                state.update(step=step, glitch=True)
                await ctx.save_checkpoint(state)
                raise TransientError("network_error", host=HOST)
            case EntityKind.NAME | EntityKind.USERNAME | EntityKind.EMAIL:
                return
            case _ if step == 4 and "failed" not in state:
                state.update(step=step, failed=True)
                await ctx.save_checkpoint(state)
                raise SourceUnavailable("source_unavailable", host=HOST)
