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
from narcisse.normalize import DEFAULT_PHONE_REGION

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


def describe(number: str) -> tuple[str, dict[str, str]]:
    """A sentence about a number, and the same as attributes."""
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
        return (
            "Numéro qui n’est attribué à personne d’après le plan de numérotation "
            "(réservé, fictif ou mal saisi).",
            attributes,
        )
    code, label = KINDS.get(phonenumbers.number_type(parsed), ("unknown", "Numéro"))
    attributes["type"] = code
    parts = [label]
    country = geocoder.country_name_for_number(parsed, "fr")
    if country:
        attributes["country"] = country
        parts.append(country)
    region = geocoder.description_for_number(parsed, "fr")
    if region and region != country:
        attributes["region"] = region
        parts.append(region)
    operator = carrier.name_for_number(parsed, "fr")
    sentence = ", ".join(parts) + "."
    if operator:
        attributes["carrier"] = operator
        sentence += (
            f" Opérateur d’origine : {operator} (le numéro a pu changer d’opérateur depuis)."
        )
    return sentence, attributes


class Phone(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="phone",
        title="Numéro de téléphone (analyse locale)",
        description=(
            "Ce qu’un numéro dit de lui-même, sans rien demander à personne : mobile ou fixe, "
            "pays, région d’un fixe, opérateur d’origine. L’analyse se fait sur ta machine."
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
        sentence, attributes = describe(target.normalized)
        yield Finding(
            kind=EntityKind.PHONE,
            value=target.normalized,
            relation="described_as",
            excerpt=sentence,
            attributes=attributes,
        )
        await ctx.progress(1, 1)
