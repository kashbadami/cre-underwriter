"""
The regulatory overlay: what governs the rent on this address, and what it costs
to sell it.

What is automatic here and what is not, stated up front because it is the whole
question a reader will have:

AUTOMATIC (fetched from the LA County Assessor, then reasoned over)
    jurisdiction, year built, unit count, and from those a DERIVED
    determination of LA City RSO coverage, AB 1482 applicability, and
    Costa-Hawkins vacancy decontrol. Plus the ULA transfer tax, which is
    arithmetic on the price once the jurisdiction is known.

MANUAL (no public API answers per parcel; the tool gives you the URL)
    The authoritative RSO determination. ZIMAS is an Angular application that
    returns an identical 15KB shell for every AIN — there is no server-rendered
    parcel page to parse and no documented service behind it. LAHD publishes no
    per-parcel RSO endpoint and there is no rent-stabilisation dataset on
    data.lacity.org. Checked 2 September 2026.

    Also manual: the certificate of occupancy date (the statutory test, which is
    not the Assessor's year built), any density-bonus or covenanted affordable
    restrictions, substantial-rehabilitation and luxury exemptions, Santa
    Monica's coverage cut-off, and SB 79 transit exposure.

The determinations below are DERIVED, and the difference between DERIVED and
AUTO matters: nobody fetched an RSO status. The tool applied the statutory test
to a year built that came from an assessment roll. That is a strong indication
and it is not a determination. Every one of them carries the URL for the check
that would make it one.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .provenance import Caveat, Value, derived, manual, missing

ZIMAS_URL = "https://zimas.lacity.org/"
LAHD_RSO_URL = "https://housing.lacity.gov/rso-rent-increase-calculator"
SM_URL = "https://www.santamonica.gov/maximum-lawful-rent"

LA_CITY_NAMES = ("LOS ANGELES",)
SANTA_MONICA_NAMES = ("SANTA MONICA",)


@dataclass
class Overlay:
    fields: Dict[str, Value] = field(default_factory=dict)
    caveats: List[Caveat] = field(default_factory=list)
    order: List[str] = field(default_factory=list)
    kinds: Dict[str, str] = field(default_factory=dict)

    def add(self, key: str, value: Value, kind: str = "auto") -> None:
        self.fields[key] = value
        self.order.append(key)
        self.kinds[key] = kind

    def as_dict(self) -> dict:
        return {
            "fields": {k: v.as_dict() for k, v in self.fields.items()},
            "caveats": [{"severity": c.severity, "text": c.text} for c in self.caveats],
        }

    def to_markdown(self) -> str:
        L = ["## Regulatory overlay", "", "| Field | Finding | Provenance |", "| --- | --- | --- |"]
        for k in self.order:
            v = self.fields[k]
            shown = v.value if v.is_known else "—"
            if isinstance(shown, (int, float)) and not isinstance(shown, bool):
                kind = self.kinds.get(k, "auto")
                if kind == "usd":
                    shown = f"${shown:,.0f}"
                elif kind == "pct":
                    shown = f"{shown:.2f}%"
                else:
                    shown = f"{shown:,.2f}"
            L.append(f"| {k.replace('_', ' ')} | {shown} | {v.label()} |")
        L.append("")
        for k in self.order:
            v = self.fields[k]
            if v.note:
                L.append(f"- *{k.replace('_', ' ')}*: {v.note}")
        L.append("")
        return "\n".join(L)


def _city_of(deal, parcel) -> Optional[str]:
    if parcel and parcel.get("situs_city"):
        return str(parcel["situs_city"]).upper()
    if deal.city is not None and deal.city.is_known:
        return str(deal.city.value).upper()
    return None


def _is(city: Optional[str], names) -> bool:
    return bool(city) and any(n in city for n in names)


def overlay_for(deal, statutes, parcel=None, fetch=True, timeout=20, cache_dir=None) -> Overlay:
    """Build the overlay. `fetch` is accepted for symmetry with the rest of the
    package; nothing here fetches, because nothing here can. See module docstring.
    """
    ov = Overlay()
    today = dt.date.today()
    city = _city_of(deal, parcel)
    units = deal.units.value if deal.units.is_known else None
    year = deal.year_built.value if deal.year_built.is_known else None
    price = float(deal.price.value) if deal.price.is_known else None

    # -- jurisdiction ----------------------------------------------------

    if city:
        src = (
            parcel and "https://portal.assessor.lacounty.gov/api/parceldetail"
        ) or "user input"
        ov.add(
            "jurisdiction",
            derived(
                city.replace(" CA", "").title(),
                note=(
                    "From the Assessor's situs city. This is a POSTAL designation. "
                    "A 'Los Angeles' mailing address can sit in unincorporated LA "
                    "County or in another incorporated city, and the rent-control "
                    "regime differs in each. Confirm the incorporated city at "
                    f"{ZIMAS_URL} before acting on anything below."
                )
                if _is(city, LA_CITY_NAMES)
                else f"From the Assessor's situs city ({src}).",
            ),
        )
        ov.caveats.append(
            Caveat(
                "material",
                "Jurisdiction is inferred from a postal city name, not from a "
                "municipal boundary lookup. Everything in this section depends on "
                "it. Confirm the parcel is inside the incorporated city before "
                "relying on any determination here.",
            )
        )
    else:
        ov.add("jurisdiction", missing("no city on the parcel record or in the input"))

    _la_rso(ov, statutes, city, units, year, today)
    _costa_hawkins(ov, statutes, city, year)
    _ab_1482(ov, statutes, city, units, year, today)
    _santa_monica(ov, statutes, city, year)
    _sb_79(ov, statutes, parcel)
    _ula(ov, statutes, city, price)

    ov.caveats.extend(
        statutes.all_caveats(
            ["la_city_rso", "costa_hawkins", "ab_1482", "santa_monica_rso", "sb_79", "ula"],
            today=today,
        )
    )
    return ov


# -- LA City RSO ----------------------------------------------------------


def _la_rso(ov, statutes, city, units, year, today) -> None:
    sec = statutes.section("la_city_rso")
    cutoff = dt.date.fromisoformat(sec["applies_if_built_on_or_before"])

    if not _is(city, LA_CITY_NAMES):
        ov.add(
            "la_city_rso_status",
            derived(
                "Not applicable — parcel is not in the City of Los Angeles",
                note="The LA City RSO is municipal. Other jurisdictions have their "
                "own ordinances; LA County's RSTPO covers unincorporated areas.",
            ),
        )
        return

    if year is None:
        ov.add(
            "la_city_rso_status",
            missing(
                f"no year built available, and the RSO test is a date. Look the "
                f"parcel up at {ZIMAS_URL}"
            ),
        )
        return

    covered = int(year) <= cutoff.year and not (int(year) == cutoff.year)
    # The statutory test is a certificate of occupancy on or before 1 Oct 1978.
    # A year built of exactly 1978 straddles it and the Assessor carries no month.
    if int(year) == cutoff.year:
        verdict = "INDETERMINATE — built 1978, and the cut-off falls inside that year"
        tag_note = (
            f"The test is a certificate of occupancy on or before "
            f"{cutoff.isoformat()}. The Assessor carries a year, not a date, so a "
            f"1978 building cannot be resolved from this source. Pull the "
            f"certificate of occupancy."
        )
    elif covered:
        verdict = "LIKELY COVERED by the LA City RSO"
        tag_note = (
            f"Year built {year} is on or before the {cutoff.isoformat()} cut-off and "
            f"the parcel carries {units if units is not None else 'an unknown number of'} "
            f"units. NOT a determination: the statutory test is the certificate of "
            f"occupancy date, not the Assessor's year built, and the tool does not "
            f"check the exemptions (government-owned, transient occupancy, "
            f"substantial rehabilitation, luxury, and others). Confirm at {ZIMAS_URL}."
        )
    else:
        verdict = "LIKELY NOT COVERED by the LA City RSO"
        tag_note = (
            f"Year built {year} is after the {cutoff.isoformat()} cut-off. Post-1978 "
            f"construction is outside the RSO. Note this cuts both ways: it also "
            f"means no vacancy-decontrol upside to buy, because there is no "
            f"stabilised rent to reset. Replacement units built on a site where RSO "
            f"units were demolished can carry their own restrictions that a year "
            f"built will not reveal — confirm at {ZIMAS_URL}."
        )

    if units is not None and units < 2:
        verdict += " — but the RSO covers buildings of two or more units"

    ov.add("la_city_rso_status", derived(verdict, note=tag_note))

    if covered:
        v = statutes.value("la_city_rso", "allowable_increase_pct", "allowable_increase_source")
        v.note = (
            f"Applies {sec['allowable_increase_period']}. The ordinance formula runs "
            f"{sec['formula_range_pct'][0]}–{sec['formula_range_pct'][1]}%. "
            + sec["utility_surcharge_note"].strip()
        )
        ov.add("la_city_rso_allowable_increase_pct", v, "pct")

    ov.add(
        "la_city_rso_determination",
        manual(
            "not fetched",
            source=ZIMAS_URL,
            note=(
                "The authoritative status. ZIMAS is a single-page application that "
                "returns an identical shell for every AIN, LAHD publishes no "
                "per-parcel endpoint, and data.lacity.org carries no rent "
                "stabilisation dataset (all checked 2026-09-02). Search the address "
                f"at {ZIMAS_URL}, or use the LAHD calculator at {LAHD_RSO_URL}."
            ),
        ),
    )


# -- Costa-Hawkins -------------------------------------------------------


def _costa_hawkins(ov, statutes, city, year) -> None:
    sec = statutes.section("costa_hawkins")
    ov.add(
        "costa_hawkins_vacancy_decontrol",
        manual(
            "Yes — statewide",
            source="Civ. Code 1954.50 et seq.",
            note=(
                "A stabilised unit resets to market rent on vacancy. This is state "
                "law and a city cannot repeal it; statewide repeal was rejected at "
                f"the ballot in {', '.join(str(y) for y in sec['statewide_repeal_attempts_rejected'])}. "
                "It is what makes turnover, not the allowable annual increase, the "
                "engine of value in rent-stabilised stock — and therefore what makes "
                "the in-place-to-market rent gap the number to underwrite."
            ),
        ),
    )
    if year is not None and int(year) > 1978:
        ov.add(
            "costa_hawkins_relevance",
            derived(
                "Low — post-1978 construction has no stabilised rent to decontrol",
                note="Vacancy decontrol is only worth something where a rent is held "
                "below market by an ordinance. Where it is not, turnover upside is "
                "an ordinary market question.",
            ),
        )


# -- AB 1482 -------------------------------------------------------------


def _ab_1482(ov, statutes, city, units, year, today) -> None:
    sec = statutes.section("ab_1482")
    window = int(sec["applies_if_age_years_at_least"])

    if year is None:
        ov.add("ab_1482_status", missing("no year built; the test is building age"))
        return

    age = today.year - int(year)
    exempt_until = int(year) + window
    rso_line = ov.fields.get("la_city_rso_status")
    likely_rso = bool(rso_line and rso_line.is_known and "LIKELY COVERED" in str(rso_line.value))

    if age < window:
        verdict = f"EXEMPT until about {exempt_until} — building is {age} years old"
        note = (
            f"AB 1482 exempts housing certificated within the previous {window} years, "
            f"and the window ROLLS: this building ages into coverage around "
            f"{exempt_until}. {sec['applies_if_age_note'].strip()} "
            f"Age here is computed from the Assessor's year built, not the "
            f"certificate of occupancy."
        )
    elif likely_rso:
        verdict = "SUPERSEDED — the local RSO governs where it is stricter"
        note = (
            "AB 1482 is a statewide floor for property not covered by a local "
            "ordinance. Where LA City RSO applies, its cap governs. Confirm the RSO "
            "status first; if the RSO determination comes back negative, AB 1482 "
            "applies instead."
        )
    else:
        verdict = f"LIKELY APPLIES — building is {age} years old and outside the local RSO"
        note = (
            f"Cap is {sec['cap_formula']}. {sec['sfr_condo_exemption'].strip()} "
            f"Both statutes sunset {sec['sunset']}."
        )

    ov.add("ab_1482_status", derived(verdict, note=note))

    if age >= window and not likely_rso:
        v = statutes.value("ab_1482", "la_county_current_max_pct", "la_county_current_max_source")
        v.note = (
            f"{sec['la_county_current_max_basis']}, for increases "
            f"{sec['la_county_current_max_period']} (prior year: "
            f"{sec['la_county_prior_year_pct']}%). {sec['cpi_timing_rule'].strip()}"
        )
        ov.add("ab_1482_max_increase_pct", v, "pct")


# -- Santa Monica --------------------------------------------------------


def _santa_monica(ov, statutes, city, year) -> None:
    if not _is(city, SANTA_MONICA_NAMES):
        return
    sec = statutes.section("santa_monica_rso")

    ov.add(
        "santa_monica_regime",
        derived(
            "Separate rent control — Santa Monica, not the LA City RSO",
            note="Santa Monica administers its own ordinance with its own coverage "
            "test, its own adjustment formula and its own registration. Nothing in "
            "the LA City section applies.",
        ),
    )
    ov.add(
        "santa_monica_coverage_cutoff",
        manual(
            "not in this tool's config",
            source=SM_URL,
            note="Santa Monica's coverage cut-off date is not carried in "
            "config/statutes.yaml and is not inferred here. Look it up before "
            "assuming a building is or is not covered.",
        ),
    )
    v = statutes.value("santa_monica_rso", "general_adjustment_pct", "source")
    v.note = (
        f"Effective {sec['general_adjustment_effective']}. Basis: {sec['basis'].strip()}"
    )
    ov.add("santa_monica_general_adjustment_pct", v, "pct")
    ov.add(
        "santa_monica_dollar_cap_monthly",
        manual(
            sec["dollar_cap_monthly_usd"],
            source=SM_URL,
            note=sec["effective_pct_note"].strip(),
        ),
        "usd",
    )
    ov.caveats.append(
        Caveat(
            "material",
            "Santa Monica: the headline adjustment is capped in dollars, so on "
            f"higher-rent units the effective percentage is materially lower than "
            f"{sec['general_adjustment_pct']}%. A model applying the headline rate "
            "flat over-states income. " + sec["effective_pct_note"].strip(),
        )
    )


# -- SB 79 ---------------------------------------------------------------


def _sb_79(ov, statutes, parcel) -> None:
    # The config section is read only to assert it is still flagged unverified.
    # If somebody ever verifies it, this function needs rewriting rather than
    # silently starting to emit a determination.
    if not statutes.is_unverified("sb_79"):
        raise RuntimeError(
            "config/statutes.yaml no longer marks sb_79 unverified. This function "
            "refuses to determine SB 79 exposure and must be rewritten before the "
            "config change takes effect."
        )
    latlon = ""
    if parcel and parcel.get("latitude") and parcel.get("longitude"):
        latlon = f" Parcel is at {parcel['latitude']:.5f}, {parcel['longitude']:.5f}."

    ov.add(
        "sb_79_transit_upzoning_exposure",
        manual(
            "not determined",
            source="config/statutes.yaml — marked unverified",
            note=(
                "Requires transit-stop proximity and the local zoning capacity test, "
                "neither of which this tool reads. The exclusion mechanism recorded "
                "in the config is explicitly flagged unverified: it was described by "
                "a practitioner and was NOT confirmed against the statute text. Do "
                "not price SB 79 exposure off this tool." + latlon
            ),
        ),
    )
    # No caveat is raised here on purpose: Statutes.caveats() already emits a
    # blocking one straight off the config's `unverified` flag, and two lines
    # saying the same thing reads as padding.


# -- Measure ULA ---------------------------------------------------------


def _ula(ov, statutes, city, price) -> None:
    sec = statutes.section("ula")

    if not _is(city, LA_CITY_NAMES):
        ov.add(
            "ula_transfer_tax",
            derived(
                "Not applicable — Measure ULA is City of Los Angeles only",
                note="The base county documentary transfer tax still applies.",
            ),
        )
        return
    if price is None:
        ov.add("ula_transfer_tax", missing("needs a price"))
        return

    tiers = sec["tiers_fy_2026_27"]
    rate = 0.0
    for t in tiers:
        lo, hi = t["from_usd"], t["to_usd"]
        if price >= lo and (hi is None or price <= hi):
            rate = float(t["rate_pct"])
            break

    lowest = min(t["from_usd"] for t in tiers)
    base_pct = float(sec["base_dtt_la_city_pct"]) + float(sec["base_dtt_la_county_pct"])
    base_amt = price * base_pct / 100.0

    if rate == 0.0:
        ov.add(
            "ula_transfer_tax",
            derived(
                0.0,
                note=(
                    f"${price:,.0f} is below the ${lowest:,.0f} threshold, so no ULA "
                    f"is due on a transfer at this price. Headroom to the threshold: "
                    f"${lowest - price:,.0f}."
                ),
            ),
            "usd",
        )
    else:
        amt = price * rate / 100.0
        ov.add(
            "ula_transfer_tax",
            derived(
                amt,
                note=(
                    f"{rate:g}% of the ENTIRE consideration, not the increment above "
                    f"the threshold — ${price:,.0f} x {rate:g}%. Paid by the "
                    f"{sec['paid_by']}. Tiers indexed {sec['indexation']}."
                ),
            ),
            "usd",
        )
        ov.add(
            "ula_effective_rate_on_price_pct",
            derived(rate, note="flat on the whole price; there is no marginal band"),
            "pct",
        )

    ov.add(
        "base_documentary_transfer_tax",
        derived(
            base_amt,
            note=f"City {sec['base_dtt_la_city_pct']}% + County "
            f"{sec['base_dtt_la_county_pct']}% = {base_pct:g}% of consideration. "
            f"Separate from, and additional to, ULA. Source: {sec['base_dtt_source']}",
        ),
        "usd",
    )
    ov.add(
        "ula_exemptions",
        manual(
            "not checked",
            source=sec["exemptions_source"],
            note=sec["exemptions_note"].strip()
            + f" Confidence on this list: {sec['exemptions_confidence']}",
        ),
    )
