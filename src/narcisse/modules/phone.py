"""What a phone number says of itself, without asking anyone: a mobile or a landline, its
country, a landline's region, the carrier it was first given to.

Read on the machine with libphonenumber (Google, Apache-2.0), whose data ships with the package:
no request leaves. A number may have moved to another carrier since: that is what its prefix says,
not who serves it today.
"""

from collections.abc import AsyncIterator
from typing import ClassVar

import phonenumbers
from phonenumbers import PhoneNumberType, carrier, geocoder

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    InputRejected,
    ModuleContext,
    ModuleMeta,
    SourceModule,
    Target,
)
from narcisse.i18n import LANGS
from narcisse.normalize import DEFAULT_PHONE_REGION
from narcisse.notes import Note, note

KINDS = {
    PhoneNumberType.MOBILE: ("mobile", "Mobile"),
    PhoneNumberType.FIXED_LINE: ("fixed_line", "Fixe"),
    PhoneNumberType.FIXED_LINE_OR_MOBILE: ("fixed_or_mobile", "Fixe ou mobile"),
    PhoneNumberType.VOIP: ("voip", "Téléphonie par internet"),
    PhoneNumberType.TOLL_FREE: ("toll_free", "Numéro gratuit"),
    PhoneNumberType.PREMIUM_RATE: ("premium_rate", "Numéro surtaxé"),
    PhoneNumberType.SHARED_COST: ("shared_cost", "Numéro à coût partagé"),
    PhoneNumberType.PERSONAL_NUMBER: ("personal_number", "Numéro personnel"),
    PhoneNumberType.UAN: ("uan", "Numéro d’entreprise"),
    PhoneNumberType.VOICEMAIL: ("voicemail", "Messagerie vocale"),
    PhoneNumberType.PAGER: ("pager", "Bipeur"),
}


def describe(number: str) -> tuple[Note, dict[str, str]]:
    """What a number says of itself (a note), and the same as attributes."""
    try:
        parsed = phonenumbers.parse(number, DEFAULT_PHONE_REGION)
    except phonenumbers.NumberParseException as exc:
        raise InputRejected("phone_unreadable") from exc
    if not phonenumbers.is_possible_number(parsed):
        raise InputRejected("phone_unreadable")
    attributes = {
        "international": phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
    }
    if not phonenumbers.is_valid_number(parsed):
        attributes["valid"] = "no"
        return note("phone_unassigned"), attributes
    code, _ = KINDS.get(phonenumbers.number_type(parsed), ("unknown", "Numéro"))
    attributes["type"] = code
    # Places named in both languages; the attributes keep the French ones.
    country = {lang: geocoder.country_name_for_number(parsed, lang) for lang in LANGS}
    if country["fr"]:
        attributes["country"] = country["fr"]
    region = {lang: geocoder.description_for_number(parsed, lang) for lang in LANGS}
    if not region["fr"] or region["fr"] == country["fr"]:
        region = {}
    else:
        attributes["region"] = region["fr"]
    operator = carrier.name_for_number(parsed, "fr")
    if operator:
        attributes["carrier"] = operator
    said = note(
        "phone_described",
        type=code,
        country=country if country["fr"] else None,
        region=region or None,
        carrier=operator or None,
    )
    return said, attributes


class Phone(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="phone",
        title={
            "fr": "Numéro de téléphone (analyse locale)",
            "en": "Phone number (local analysis)",
        },
        description=(
            {
                "fr": (
                    "Ce qu’un numéro dit de lui-même, sans rien demander à personne : mobile ou "
                    "fixe, pays, région d’un fixe, opérateur d’origine. L’analyse se fait sur ta "
                    "machine."
                ),
                "en": (
                    "What a number says of itself, asking no one: mobile or landline, country, a "
                    "landline's region, original carrier. The analysis happens on your machine."
                ),
            }
        ),
        category="phone",
        accepts=frozenset({EntityKind.PHONE}),
        produces=frozenset({EntityKind.PHONE}),
        max_parallel_runs=2,
        licence="libphonenumber (Google) : Apache-2.0",
        data_source="https://github.com/google/libphonenumber",
    )

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        said, attributes = describe(target.normalized)
        yield Finding(
            kind=EntityKind.PHONE,
            value=target.normalized,
            relation="described_as",
            note=said,
            attributes=attributes,
        )
        await ctx.progress(1, 1)
