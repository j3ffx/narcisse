"""Which traces may become new starting points: suggested to the user, or followed by a scan.

A trace becomes a lead when it is of a kind sources can search from, isn't already one of the
profile's elements, and is sure enough. The user adds a suggested one as an element, or dismisses
it. A profile may also let scans follow the surest ones by themselves, up to a depth, within a
cap per scan, never from a rejected trace.
"""

from narcisse.domain import EntityKind, EntityStatus
from narcisse.storage.models import Entity

# What sources can search from. Names (homonyms), organisations (other people's companies),
# pages and leaks lead nowhere useful, or to other people.
PIVOT_KINDS = frozenset(
    {
        EntityKind.EMAIL,
        EntityKind.USERNAME,
        EntityKind.DOMAIN,
        EntityKind.PHONE,
        EntityKind.ACCOUNT,
    }
)
SUGGEST_FROM = 0.6  # confidence from which a trace is suggested
FOLLOW_FROM = 0.7  # … and from which a scan follows it by itself, when the profile allows
MAX_DEPTH = 2  # hops a scan may follow
MAX_PIVOTS = 25  # traces one scan may follow


def is_lead(entity: Entity, declared: bool, threshold: float = SUGGEST_FROM) -> bool:
    """Whether the trace could be a new starting point (and is sure enough for `threshold`)."""
    if declared or entity.pivot_dismissed or entity.kind not in PIVOT_KINDS:
        return False
    if entity.status == EntityStatus.FALSE_POSITIVE:
        return False
    return entity.status == EntityStatus.CONFIRMED or (entity.confidence or 0.0) >= threshold


def to_follow(entity: Entity, declared: bool) -> bool:
    return is_lead(entity, declared, FOLLOW_FROM)


def depth_allowed(settings: dict[str, object]) -> int:
    value = settings.get("pivot_depth", 0)
    return max(0, min(MAX_DEPTH, value if isinstance(value, int) else 0))
