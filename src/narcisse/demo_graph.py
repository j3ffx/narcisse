"""A fictitious profile with thousands of traces, for the demo and for measuring the graph.

The traces look like what the sources find (accounts, the sites and names they show, addresses
shared between accounts) so that the graph has the shape of a real one: chains and crossings,
not a star. Everything is made up, on reserved domains, and only demo mode offers it.
"""

import random
from collections import deque
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.domain import EntityKind, EntityStatus, ProfileKind, RunStatus, ScanStatus, SeedStatus
from narcisse.engine.engine import IDENTITY_KEY
from narcisse.normalize import normalize
from narcisse.storage.models import Edge, Entity, Evidence, ModuleRun, Profile, Scan, Seed

MODULE = "demo.fake"
WORDS = (
    "forum", "photos", "code", "musique", "blog", "annonces", "jeux", "recettes", "voyage",
    "sport", "cinema", "lecture", "jardin", "velo", "rando", "radio", "atelier", "galerie",
    "carnet", "agenda", "reseau", "club", "salon", "marche", "studio", "archives", "quartier",
    "podcast", "dessin", "theatre",
)  # fmt: skip
FIRST = ("jeanne", "paul", "lea", "hugo", "nina", "louis", "chloe", "arthur", "emma", "jules")
LAST = ("exemple", "fictif", "modele", "essai", "specimen")
TLDS = ("org", "com", "net")
EXCERPT = "Trace fictive, générée pour la démonstration du graphe."


def _platforms(rng: random.Random) -> list[str]:
    """Fictitious sites: « https://forum.example.org/{h} »."""
    return [
        f"https://{word}.example.{rng.choice(TLDS)}/" + rng.choice(("{h}", "@{h}", "u/{h}"))
        for word in WORDS
    ]


class _Builder:
    def __init__(self, profile: Profile, now: datetime, size: int) -> None:
        self.profile = profile
        self.now = now
        self.size = size
        self.entities: dict[tuple[EntityKind, str], Entity] = {}
        self.edges: set[tuple[int, int, str]] = set()
        self.pending: list[tuple[Entity, Entity, str, float]] = []

    @property
    def full(self) -> bool:
        return len(self.entities) >= self.size

    def entity(
        self,
        kind: EntityKind,
        value: str,
        rng: random.Random,
        *,
        status: EntityStatus | None = None,
        normalized: str | None = None,
    ) -> tuple[Entity, bool]:
        display, normal = normalize(kind, value)
        normalized = normalized or normal
        key = (kind, normalized)
        if key in self.entities:
            return self.entities[key], False
        seen = self.now - timedelta(days=rng.randint(0, 720))
        entity = Entity(
            profile_id=self.profile.id,
            kind=kind,
            normalized=normalized,
            display=display,
            status=status
            or rng.choices(
                (EntityStatus.UNREVIEWED, EntityStatus.CONFIRMED, EntityStatus.FALSE_POSITIVE),
                weights=(80, 15, 5),
            )[0],
            confidence=round(rng.uniform(0.2, 0.95), 2),
            attributes={},
            first_seen=seen,
            last_seen=min(self.now, seen + timedelta(days=rng.randint(0, 200))),
        )
        self.entities[key] = entity
        return entity, True

    def relate(self, source: Entity, target: Entity, relation: str, confidence: float) -> None:
        self.pending.append((source, target, relation, confidence))


async def generate(session: AsyncSession, *, size: int, now: datetime) -> Profile:
    """A new profile of about `size` fictitious traces, with one finished scan holding them."""
    rng = random.Random(size)  # the same graph for the same size: measures can be compared
    profile = Profile(
        name=f"Graphe fictif ({size} traces)",
        kind=ProfileKind.MIXED,
        settings={},
        created_at=now,
        updated_at=now,
    )
    session.add(profile)
    await session.flush()
    build = _Builder(profile, now, size)
    identity, _ = build.entity(
        EntityKind.IDENTITY,
        profile.name,
        rng,
        status=EntityStatus.CONFIRMED,
        normalized=IDENTITY_KEY,
    )
    platforms = _platforms(rng)
    handles = [f"{f}.{rng.choice(LAST)}" for f in FIRST]

    queue: deque[Entity] = deque()
    seeds = (
        [(EntityKind.NAME, "Jeanne Exemple")]
        + [(EntityKind.USERNAME, h) for h in handles[:4]]
        + [(EntityKind.EMAIL, f"{h}@example.org") for h in handles[:3]]
        + [(EntityKind.DOMAIN, "jeanne.example.org")]
    )
    for kind, value in seeds:
        entity, _ = build.entity(kind, value, rng, status=EntityStatus.CONFIRMED)
        display, normalized = normalize(kind, value)
        session.add(
            Seed(
                profile=profile,
                kind=kind,
                value=display,
                normalized=normalized,
                status=SeedStatus.WATCH,
                created_at=now,
            )
        )
        build.relate(identity, entity, "declares", 1.0)
        queue.append(entity)

    # Each trace carries the handle it was found under; what it leads to mostly keeps it, as a
    # person reuses a username: the graph grows in clusters, joined by the few shared traces.
    handle_of: dict[int, str] = {id(e): handles[0] for e in build.entities.values()}
    for (kind, value), entity in zip(seeds, list(build.entities.values())[1:], strict=True):
        handle_of[id(entity)] = value.split("@")[0] if kind != EntityKind.NAME else handles[0]

    def variant(handle: str) -> str:
        roll = rng.random()
        if roll < 0.75:
            return handle
        if roll < 0.95:
            return f"{handle.split('.')[0].rstrip('0123456789')}{rng.randint(1, 99)}"
        return rng.choice(handles)  # the odd link to another cluster

    def name_of(handle: str) -> str:
        """The name a profile under that handle would show (« jeanne.essai » → Jeanne Essai)."""
        first, _, last = handle.partition(".")
        last = last.rstrip("0123456789") or rng.choice(LAST)
        return f"{first.rstrip('0123456789').capitalize()} {last.capitalize()}"

    def add(parent: Entity, kind: EntityKind, value: str, relation: str, handle: str) -> None:
        child, new = build.entity(kind, value, rng)
        if child is parent:
            return
        build.relate(parent, child, relation, rng.uniform(0.3, 0.9))
        if new:
            handle_of[id(child)] = handle
            if kind != EntityKind.URL:
                queue.append(child)

    def grow(parent: Entity) -> None:
        own = handle_of.get(id(parent), handles[0])
        match parent.kind:
            case EntityKind.USERNAME | EntityKind.EMAIL | EntityKind.NAME:
                for _ in range(rng.randint(2, 7)):
                    handle = variant(own)
                    url = rng.choice(platforms).format(h=handle)
                    add(parent, EntityKind.ACCOUNT, url, "has_account", handle)
            case EntityKind.ACCOUNT:
                handle = variant(own)
                options = (
                    (EntityKind.NAME, name_of(handle), "shows_name"),
                    (EntityKind.EMAIL, f"{handle}@example.com", "shows_email"),
                    (EntityKind.USERNAME, handle, "uses_username"),
                    (
                        EntityKind.URL,
                        f"https://{rng.choice(WORDS)}.example.net/{handle}",
                        "links_to",
                    ),
                    (EntityKind.ACCOUNT, rng.choice(platforms).format(h=handle), "links_to"),
                )
                for kind, value, relation in rng.sample(options, k=rng.choice((0, 1, 1, 2, 3))):
                    add(parent, kind, value, relation, handle)
            case EntityKind.DOMAIN:
                for page in rng.sample(WORDS, k=4):
                    add(parent, EntityKind.URL, f"https://{parent.display}/{page}", "links_to", own)

    while queue and not build.full:
        grow(queue.popleft())
        if not queue and not build.full:
            # Everything led nowhere new: start again from another username.
            fresh = f"{rng.choice(FIRST)}.{rng.choice(LAST)}{rng.randint(100, 999)}"
            extra, _ = build.entity(EntityKind.USERNAME, fresh, rng)
            handle_of[id(extra)] = fresh
            build.relate(identity, extra, "uses_username", 0.5)
            queue.append(extra)

    session.add_all(build.entities.values())
    await session.flush()
    scan = Scan(
        profile=profile,
        status=ScanStatus.DONE,
        modules=[MODULE],
        results_count=0,
        created_at=now,
        finished_at=now,
    )
    session.add(scan)
    await session.flush()
    run = ModuleRun(
        scan_id=scan.id,
        module=MODULE,
        input_entity_id=identity.id,
        status=RunStatus.DONE,
        progress_done=1,
        progress_total=1,
        results_count=0,
        attempts=1,
        retryable=False,
        created_at=now,
        started_at=now,
        finished_at=now,
        updated_at=now,
    )
    session.add(run)
    await session.flush()
    edges: list[Edge] = []
    for source, target, relation, confidence in build.pending:
        if (source.id, target.id, relation) in build.edges:
            continue
        build.edges.add((source.id, target.id, relation))
        edges.append(
            Edge(
                profile_id=profile.id,
                source_id=source.id,
                target_id=target.id,
                relation=relation,
                module="seed" if relation == "declares" else MODULE,
                confidence=round(confidence, 2),
                first_seen=target.first_seen,
                last_seen=target.last_seen,
            )
        )
    session.add_all(edges)
    await session.flush()
    shown = {entity.id: entity for entity in build.entities.values()}
    proofs = [
        Evidence(
            entity_id=edge.target_id,
            edge_id=edge.id,
            scan_id=scan.id,
            run_id=run.id,
            module=MODULE,
            url=shown[edge.source_id].display
            if shown[edge.source_id].kind == EntityKind.ACCOUNT
            else None,
            excerpt=EXCERPT,
            content_hash=None,
            captured_at=edge.first_seen,
        )
        for edge in edges
        if edge.module == MODULE
    ]
    session.add_all(proofs)
    scan.results_count = run.results_count = len(proofs)
    await session.flush()
    return profile
