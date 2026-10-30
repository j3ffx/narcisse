"""The settings of the sources and of the assistant. Tokens are written, never read back."""

from dataclasses import replace
from urllib.parse import urlsplit

from fastapi import APIRouter

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind
from narcisse.errors import AppError
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
        searxng_url=preferences.searxng_url,
        searxng_autostart=preferences.searxng_autostart,
        llm_provider=preferences.llm_provider,
        llm_model=preferences.llm_model,
        llm_remote_ok=preferences.llm_remote_ok,
    )


def _instances(values: list[str]) -> tuple[str, ...]:
    """Host names, once each, in the order given (`invalid_value` for one that isn't)."""
    hosts = (normalize(EntityKind.DOMAIN, value)[1] for value in values if value.strip())
    return tuple(dict.fromkeys(hosts))


def _searxng(value: str | None) -> str | None:
    """An instance's address (`http://127.0.0.1:8888`), without a trailing slash; None to remove."""
    value = (value or "").strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AppError("invalid_searxng_url", status=422)
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"


@router.get("/preferences")
async def get_preferences(s: ServicesDep) -> PreferencesOut:
    return _out(Preferences.load(s.settings.preferences_path))


@router.patch("/preferences")
async def update_preferences(body: PreferencesPatch, s: ServicesDep) -> PreferencesOut:
    path = s.settings.preferences_path
    preferences = Preferences.load(path)
    changes = body.model_dump(exclude_unset=True)
    for key in (
        "exclude_adult",
        "fediverse_instances",
        "searxng_autostart",
        "llm_provider",
        "llm_remote_ok",
    ):
        if key in changes and changes[key] is None:
            del changes[key]
    for key in TOKENS:
        if key in changes:
            changes[key] = (changes[key] or "").strip() or None
    if "searxng_url" in changes:
        changes["searxng_url"] = _searxng(changes["searxng_url"])
    if "fediverse_instances" in changes:
        changes["fediverse_instances"] = _instances(changes["fediverse_instances"])
    if changes.get("llm_provider") not in (None, *s.assistant.providers()):
        raise AppError("llm_provider_unavailable", status=422)
    if "llm_model" in changes:
        changes["llm_model"] = (changes["llm_model"] or "").strip() or None
    preferences = replace(preferences, **changes)
    preferences.save(path)
    s.assistant.forget()
    return _out(preferences)
