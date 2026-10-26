"""What the user can do about a trace: its action sheet, and the requests Narcisse prepares for
them to send (never sent from here)."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind, EntityStatus, ProfileKind, SeedStatus
from narcisse.errors import not_found
from narcisse.remediation import letters
from narcisse.remediation.actions import Action, TraceFacts, actions_for
from narcisse.remediation.knowledge import Service, guide
from narcisse.schemas import ActionOut, GuideOut, LetterOut, RemediationOut, ServiceOut
from narcisse.storage.models import Edge, Entity, Evidence, Profile, Seed

router = APIRouter(tags=["remediation"])

MAX_PAGES = 10


def _lang(action: Action) -> letters.Lang:
    """The language the recipient most likely reads: French for French sites, the search
    engines' European forms and unknown sites; English for the others."""
    service = action.service
    if service is None:
        return "fr"
    if service.category == "business_directory" or service.notes_lang == "fr":
        return "fr"
    if any(domain.endswith(".fr") for domain in service.domains):
        return "fr"
    return "en"


def _service(service: Service) -> ServiceOut:
    return ServiceOut(
        name=service.name,
        category=service.category,
        url=service.url,
        difficulty=service.difficulty,
        notes=service.notes,
        notes_lang=service.notes_lang,
        source=service.source,
    )


async def _seed_values(session: AsyncSession, profile_id: int) -> dict[str, list[str]]:
    rows = await session.execute(
        select(Seed.kind, Seed.value)
        .where(Seed.profile_id == profile_id, Seed.status == SeedStatus.WATCH)
        .order_by(Seed.id)
    )
    values: dict[str, list[str]] = {}
    for kind, value in rows:
        values.setdefault(kind, []).append(value)
    return values


@router.get("/entities/{entity_id}/remediation")
async def get_remediation(entity_id: int, s: ServicesDep) -> RemediationOut:
    async with s.db.snapshot() as session:
        entity = await session.get(Entity, entity_id)
        if entity is None:
            raise not_found("entity")
        profile = await session.get(Profile, entity.profile_id)
        if profile is None:
            raise not_found("profile")
        incoming = list(await session.scalars(select(Edge).where(Edge.target_id == entity_id)))
        rows = await session.execute(
            select(Evidence.module, Evidence.url)
            .where(Evidence.entity_id == entity_id)
            .order_by(Evidence.captured_at.desc(), Evidence.id.desc())
        )
        modules: set[str] = set()
        urls: list[str] = []
        for module, url in rows:
            modules.add(module)
            if url and url not in urls:
                urls.append(url)
        if any(edge.module == "seed" for edge in incoming):
            modules.add("seed")
        seeds = await _seed_values(session, entity.profile_id)

    kind = EntityKind(entity.kind)
    facts = TraceFacts(
        kind=kind,
        status=EntityStatus(entity.status),
        display=entity.display,
        normalized=entity.normalized,
        profile_kind=ProfileKind(profile.kind),
        modules=frozenset(modules),
        relations=frozenset(e.relation for e in incoming if e.module != "seed"),
        evidence_urls=tuple(urls),
    )
    page = (entity.display,) if kind in (EntityKind.ACCOUNT, EntityKind.URL) else ()
    pages = tuple(dict.fromkeys((*page, *urls)))[:MAX_PAGES]
    email = entity.display if kind == EntityKind.EMAIL and "seed" in modules else None
    today = s.engine.clock.now().date()

    out = []
    for action in actions_for(facts):
        context = letters.LetterContext(
            target=entity.display,
            pages=pages,
            service=action.service.name if action.service else None,
            name=next(iter(seeds.get(EntityKind.NAME, [])), None),
            email=email or next(iter(seeds.get(EntityKind.EMAIL, [])), None),
            address=next(iter(seeds.get(EntityKind.ADDRESS, [])), None),
            today=today,
        )
        rendered = {}
        if action.letter is not None:
            for lang in ("fr", "en"):
                letter = letters.render(action.letter, lang, context)
                rendered[lang] = LetterOut(subject=letter.subject, body=letter.body)
        out.append(
            ActionOut(
                code=action.code,
                service=_service(action.service) if action.service else None,
                url=action.url,
                email=action.email,
                links=[GuideOut(title=g.title, url=g.url) for g in action.links],
                letter=action.letter,
                letters=rendered,
                lang=_lang(action),
            )
        )
    complaint = guide("cnil_complaint")
    return RemediationOut(actions=out, complaint=GuideOut(title=complaint.title, url=complaint.url))
