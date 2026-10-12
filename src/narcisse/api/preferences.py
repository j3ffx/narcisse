"""The settings of the sources. Tokens are written, never read back."""

from dataclasses import replace

from fastapi import APIRouter

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind
from narcisse.normalize import normalize
from narcisse.preferences import Preferences
from narcisse.schemas import PreferencesOut, PreferencesPatch

router = APIRouter(tags=["preferences"])

TOKENS = ("github_token", "gitlab_token")


def _out(preferences: Preferences) -> PreferencesOut:
    return PreferencesOut(
        github_token_set=bool(preferences.github_token),
        gitlab_token_set=bool(preferences.gitlab_token),
        exclude_adult=preferences.exclude_adult,
        fediverse_instances=list(preferences.fediverse_instances),
    )


def _instances(values: list[str]) -> tuple[str, ...]:
    """Host names, once each, in the order given (`invalid_value` for one that isn't)."""
    hosts = (normalize(EntityKind.DOMAIN, value)[1] for value in values if value.strip())
    return tuple(dict.fromkeys(hosts))


@router.get("/preferences")
async def get_preferences(s: ServicesDep) -> PreferencesOut:
    return _out(Preferences.load(s.settings.preferences_path))


@router.patch("/preferences")
async def update_preferences(body: PreferencesPatch, s: ServicesDep) -> PreferencesOut:
    path = s.settings.preferences_path
    preferences = Preferences.load(path)
    changes = body.model_dump(exclude_unset=True)
    for key in ("exclude_adult", "fediverse_instances"):
        if key in changes and changes[key] is None:
            del changes[key]
    for key in TOKENS:
        if key in changes:
            changes[key] = (changes[key] or "").strip() or None
    if "fediverse_instances" in changes:
        changes["fediverse_instances"] = _instances(changes["fediverse_instances"])
    preferences = replace(preferences, **changes)
    preferences.save(path)
    return _out(preferences)
