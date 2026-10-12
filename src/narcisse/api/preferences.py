"""The settings of the sources. The GitHub token is written, never read back."""

from dataclasses import replace

from fastapi import APIRouter

from narcisse.api.deps import ServicesDep
from narcisse.preferences import Preferences
from narcisse.schemas import PreferencesOut, PreferencesPatch

router = APIRouter(tags=["preferences"])


def _out(preferences: Preferences) -> PreferencesOut:
    return PreferencesOut(
        github_token_set=bool(preferences.github_token),
        exclude_adult=preferences.exclude_adult,
    )


@router.get("/preferences")
async def get_preferences(s: ServicesDep) -> PreferencesOut:
    return _out(Preferences.load(s.settings.preferences_path))


@router.patch("/preferences")
async def update_preferences(body: PreferencesPatch, s: ServicesDep) -> PreferencesOut:
    path = s.settings.preferences_path
    preferences = Preferences.load(path)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("exclude_adult", False) is None:
        del changes["exclude_adult"]
    if "github_token" in changes:
        changes["github_token"] = (changes["github_token"] or "").strip() or None
    preferences = replace(preferences, **changes)
    preferences.save(path)
    return _out(preferences)
