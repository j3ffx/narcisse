"""French company registries: the companies a person runs or ran (their name, the month and year
of birth the register publishes, the registered office, often the home of a sole trader), and,
for a company, its officers, its registered office and its legal notices.

Data: the State's « API Recherche d'entreprises » (open, no key, 7 requests a second; companies
whose owners asked for their data to stay private are left out of it) and the BODACC, the official
bulletin of company notices (open data, Licence Ouverte).
"""

import re
from collections.abc import AsyncIterator, Iterator
from typing import Any, ClassVar

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleMeta,
    RateLimit,
    SourceModule,
    SourceUnavailable,
    Target,
)
from narcisse.normalize import fold

SEARCH = "https://recherche-entreprises.api.gouv.fr/search"
BODACC = (
    "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "annonces-commerciales/records"
)
SHEET = "https://annuaire-entreprises.data.gouv.fr/entreprise/"
PAGES = 2  # 25 companies a page
MAX_NOTICES = 20
MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]
_DIGITS = re.compile(r"^\d{9}(\d{5})?$")


def person_name(nom: str, prenoms: str) -> str:
    """« Jeanne Exemple » from the register's « EXEMPLE (EXEMPLE) » and « JEANNE »."""
    nom = re.sub(r"\s*\(.*?\)", "", nom or "").strip()
    return " ".join(p for p in (prenoms.strip().title(), nom.title()) if p)


def born(date: str | None) -> str:
    """« avril 1996 » from « 1996-04 »."""
    match = re.match(r"^(\d{4})-(\d{2})", date or "")
    if not match or not 1 <= int(match.group(2)) <= 12:
        return ""
    return f"{MONTHS[int(match.group(2)) - 1]} {match.group(1)}"


def public(value: Any) -> str:
    text = str(value or "").strip()
    return "" if "NON-DIFFUSIBLE" in text.upper() else text


def company(result: dict[str, Any]) -> tuple[str, str]:
    """(name with its SIREN, SIREN): one trace per company, whatever its name is written."""
    siren = str(result.get("siren") or "")
    name = public(result.get("nom_complet")) or siren
    return f"{name} ({siren})", siren


def split_name(value: str) -> tuple[str, str] | None:
    """(first name, last name) of « Jeanne Exemple »: the last word is the last name."""
    words = value.split()
    return (" ".join(words[:-1]), words[-1]) if len(words) >= 2 else None


class Companies(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="companies",
        title="Registres d’entreprises (France)",
        description=(
            "Les entreprises qu’une personne dirige ou a dirigées, ou à son nom (entrepreneur "
            "individuel) : le registre publie le mois et l’année de naissance des dirigeants et "
            "l’adresse du siège, souvent le domicile. Pour une entreprise : ses dirigeants, son "
            "siège et ses annonces au BODACC. Des homonymes sont possibles."
        ),
        category="registries",
        accepts=frozenset({EntityKind.NAME, EntityKind.ORGANIZATION}),
        produces=frozenset(
            {EntityKind.ORGANIZATION, EntityKind.NAME, EntityKind.ADDRESS, EntityKind.URL}
        ),
        hosts=("recherche-entreprises.api.gouv.fr", "bodacc-datadila.opendatasoft.com"),
        rate_limit=RateLimit(requests=2, per_seconds=1),
        max_parallel_runs=1,
        licence="Données publiques de l’État (Licence Ouverte)",
        data_source="https://recherche-entreprises.api.gouv.fr/docs/",
    )

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        return kind == EntityKind.ORGANIZATION or (
            kind == EntityKind.NAME and split_name(value) is not None
        )

    async def _search(self, ctx: ModuleContext, **params: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for page in range(1, PAGES + 1):
            response = await ctx.http.get(SEARCH, params={**params, "page": str(page)})
            if response.status_code >= 400:
                raise SourceUnavailable(
                    "source_refused",
                    host="recherche-entreprises.api.gouv.fr",
                    status=response.status_code,
                )
            answer = response.json()
            results = [r for r in answer.get("results") or [] if isinstance(r, dict)]
            found += results
            if page >= int(answer.get("total_pages") or 1) or not results:
                break
        return found

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        if target.kind == EntityKind.NAME:
            async for finding in self._person(ctx, target):
                yield finding
        else:
            async for finding in self._company(ctx, target):
                yield finding

    # A person: the companies they run, or that bear their name.

    async def _person(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        first, last = split_name(target.value) or ("", "")
        wanted_first, wanted_last = fold(first.split()[0]), fold(last)
        await ctx.progress(0, 2)
        officers = await self._search(
            ctx,
            nom_personne=last,
            prenoms_personne=first,
            type_personne="dirigeant",
            per_page="25",
        )
        await ctx.progress(1, 2)
        traders = await self._search(
            ctx, q=f"{first} {last}", est_entrepreneur_individuel="true", per_page="25"
        )
        matches: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        for result in officers:
            for officer in result.get("dirigeants") or []:
                if (
                    officer.get("type_dirigeant") == "personne physique"
                    and wanted_last in fold(str(officer.get("nom") or ""))
                    and wanted_first in fold(str(officer.get("prenoms") or "")).split()
                ):
                    matches.append((result, officer))
                    break
        seen = {company(result)[1] for result, _ in matches}
        for result in traders:
            words = fold(public(result.get("nom_complet"))).replace("(", " ").split()
            if wanted_last in words and wanted_first in words and company(result)[1] not in seen:
                matches.append((result, None))
                seen.add(company(result)[1])
        # Many companies under a common name: most are namesakes'.
        confidence = 0.4 if len(matches) <= 5 else 0.2
        for result, officer in matches:
            for finding in self._run_by(result, officer, confidence):
                yield finding
        await ctx.progress(2, 2, {"companies": len(matches)})

    def _run_by(
        self, result: dict[str, Any], officer: dict[str, Any] | None, confidence: float
    ) -> Iterator[Finding]:
        value, siren = company(result)
        name = public(result.get("nom_complet"))
        active = "en activité" if result.get("etat_administratif") == "A" else "fermée"
        created = public(result.get("date_creation"))
        office = public((result.get("siege") or {}).get("adresse"))
        if officer is not None:
            who = person_name(str(officer.get("nom") or ""), str(officer.get("prenoms") or ""))
            when = born(officer.get("date_de_naissance"))
            role = public(officer.get("qualite")) or "dirigeant"
            excerpt = (
                f"{who}, {role.lower()}{f', né·e en {when}' if when else ''}, de {name} "
                f"({active}{f', créée le {created}' if created else ''})."
            )
            relation = "company_officer"
            attributes = {"siren": siren, "role": role, "birth": officer.get("date_de_naissance")}
        else:
            excerpt = (
                f"Entreprise individuelle {name} ({active}"
                f"{f', créée le {created}' if created else ''})."
            )
            relation = "sole_trader"
            attributes = {"siren": siren}
        yield Finding(
            kind=EntityKind.ORGANIZATION,
            value=value,
            relation=relation,
            confidence=confidence,
            url=f"{SHEET}{siren}",
            excerpt=excerpt + (f" Siège : {office}." if office else ""),
            attributes={k: v for k, v in attributes.items() if v},
        )
        if office:
            yield Finding(
                kind=EntityKind.ADDRESS,
                value=office,
                relation="registered_office",
                # A sole trader's registered office is often their home.
                confidence=confidence if officer is not None else min(0.5, confidence + 0.1),
                url=f"{SHEET}{siren}",
                excerpt=f"Siège de {name}, publié au registre.",
                via=(EntityKind.ORGANIZATION, value),
            )

    # A company: its officers, its office, its notices.

    async def _company(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        digits = target.normalized.replace(" ", "")
        await ctx.progress(0, 2)
        if _DIGITS.match(digits):
            results = await self._search(ctx, q=digits[:9], per_page="1")
            result = results[0] if results else None
        else:
            wanted = fold(target.value)
            results = await self._search(ctx, q=target.value, per_page="10")
            result = next(
                (
                    r
                    for r in results
                    if wanted
                    in (
                        fold(public(r.get("nom_complet"))),
                        fold(public(r.get("nom_raison_sociale"))),
                    )
                ),
                None,
            )
        if result is None:
            await ctx.progress(2, 2, {"companies": 0})
            return
        value, siren = company(result)
        name = public(result.get("nom_complet"))
        yield Finding(
            kind=EntityKind.ORGANIZATION,
            value=value,
            relation="registered_as",
            confidence=0.9,
            url=f"{SHEET}{siren}",
            excerpt=f"{name} au registre, SIREN {siren}.",
        )
        via = (EntityKind.ORGANIZATION, value)
        office = public((result.get("siege") or {}).get("adresse"))
        if office:
            yield Finding(
                kind=EntityKind.ADDRESS,
                value=office,
                relation="registered_office",
                confidence=0.9,
                url=f"{SHEET}{siren}",
                excerpt=f"Siège de {name}, publié au registre.",
                via=via,
            )
        officers = 0
        for officer in result.get("dirigeants") or []:
            if officer.get("type_dirigeant") != "personne physique":
                continue
            who = person_name(str(officer.get("nom") or ""), str(officer.get("prenoms") or ""))
            if not public(who):
                continue
            officers += 1
            when = born(officer.get("date_de_naissance"))
            role = public(officer.get("qualite")) or "dirigeant"
            yield Finding(
                kind=EntityKind.NAME,
                value=who,
                relation="officer",
                confidence=0.5,
                url=f"{SHEET}{siren}",
                excerpt=f"{who}, {role.lower()} de {name}{f', né·e en {when}' if when else ''}.",
                via=via,
            )
        await ctx.progress(1, 2)
        notices = 0
        async for finding in self._notices(ctx, siren, name, via):
            notices += 1
            yield finding
        await ctx.progress(2, 2, {"companies": 1, "officers": officers, "notices": notices})

    async def _notices(
        self, ctx: ModuleContext, siren: str, name: str, via: tuple[EntityKind, str]
    ) -> AsyncIterator[Finding]:
        response = await ctx.http.get(
            BODACC,
            params={
                "where": f'registre like "{siren}"',
                "order_by": "dateparution desc",
                "limit": str(MAX_NOTICES),
            },
        )
        if response.status_code >= 400:
            ctx.log.info("BODACC refused: %s", response.status_code)
            return
        for notice in response.json().get("results") or []:
            url = notice.get("url_complete")
            if not url:
                continue
            what = public(notice.get("familleavis_lib")) or "Annonce"
            date = public(notice.get("dateparution"))
            court = public(notice.get("tribunal"))
            yield Finding(
                kind=EntityKind.URL,
                value=str(url),
                relation="legal_notice",
                confidence=0.9,
                url=str(url),
                excerpt=(
                    f"Annonce au BODACC{f' du {date}' if date else ''} : {what.lower()} "
                    f"({name}{f', {court.lower()}' if court else ''})."
                ),
                via=via,
            )
