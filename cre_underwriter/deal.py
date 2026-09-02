"""
The inputs to an underwriting, each one tagged with where it came from.

Everything optional is genuinely optional. A field the user did not supply and
the tool could not fetch comes back MISSING, and the arithmetic that needs it
is skipped and reported as skipped. There is no field anywhere in this module
that quietly acquires a plausible number.

The one exception is `vacancy_pct`, which carries a DEFAULT — and DEFAULT is a
loud tag: it prints as "DEFAULT — assumption" and every metric downstream of it
is listed in the report's assumptions block.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .provenance import Value, default, derived, missing, user_input

# Field name -> (json key, human label, unit)
MONEY = "usd"
PCT = "pct"
SF = "sf"
COUNT = "count"


@dataclass
class RentRollLine:
    """One unit. `rent_monthly` is contract rent, not market rent."""

    unit: str
    rent_monthly: float
    beds: Optional[float] = None
    occupied: bool = True
    market_rent_monthly: Optional[float] = None
    note: str = ""


@dataclass
class Deal:
    address: Value
    price: Value
    units: Value

    rentable_sf: Value
    building_sf_assessor: Value
    lot_sf: Value
    year_built: Value

    gross_scheduled_rent_annual: Value
    other_income_annual: Value
    vacancy_pct: Value
    operating_expenses_annual: Value  # EXCLUDING property tax and direct assessments

    property_tax_rate_pct: Value
    seller_assessed_value: Value
    direct_assessments_annual: Value

    rent_roll: List[RentRollLine] = field(default_factory=list)
    land_value: Value = None
    construction_cost_per_sf: Value = None
    soft_cost_pct: Value = None
    broker_replacement_estimate: Value = None
    city: Value = None
    ain: Value = None
    sale_date: Value = None
    notes: List[str] = field(default_factory=list)

    # -- loading ----------------------------------------------------------

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Deal":
        def inp(key, note=None):
            if key in d and d[key] is not None:
                return user_input(d[key], note=note)
            return missing(f"{key} not supplied")

        roll = [RentRollLine(**line) for line in d.get("rent_roll", [])]

        gsr = inp("gross_scheduled_rent_annual")
        if not gsr.is_known and roll:
            total = sum(l.rent_monthly for l in roll) * 12
            gsr = derived(
                total, note=f"sum of {len(roll)} rent-roll lines x 12 months"
            )

        units = inp("units")
        if not units.is_known and roll:
            units = derived(len(roll), note="count of rent-roll lines")

        vac = d.get("vacancy_pct")
        if vac is None:
            vacancy = default(
                5.0,
                "No vacancy figure supplied. 5% is a convention, not a market "
                "observation for this submarket. Supply the actual figure.",
            )
        else:
            vacancy = user_input(vac)

        return cls(
            address=inp("address"),
            price=inp("price"),
            units=units,
            rentable_sf=inp(
                "rentable_sf",
                note="net rentable area as marketed. Not the Assessor's building area.",
            ),
            building_sf_assessor=inp("building_sf_assessor"),
            lot_sf=inp("lot_sf"),
            year_built=inp("year_built"),
            gross_scheduled_rent_annual=gsr,
            other_income_annual=(
                user_input(d["other_income_annual"])
                if d.get("other_income_annual") is not None
                else default(0.0, "No other income supplied; treated as zero.")
            ),
            vacancy_pct=vacancy,
            operating_expenses_annual=inp(
                "operating_expenses_annual",
                note="must EXCLUDE property tax and direct assessments — the model adds those.",
            ),
            property_tax_rate_pct=inp(
                "property_tax_rate_pct",
                note="total ad valorem rate for the parcel's Tax Rate Area, "
                "including voter-approved debt service.",
            ),
            seller_assessed_value=inp("seller_assessed_value"),
            direct_assessments_annual=inp("direct_assessments_annual"),
            rent_roll=roll,
            land_value=inp("land_value"),
            construction_cost_per_sf=inp("construction_cost_per_sf"),
            soft_cost_pct=inp("soft_cost_pct"),
            broker_replacement_estimate=inp("broker_replacement_estimate"),
            city=inp("city"),
            ain=inp("ain"),
            sale_date=inp("sale_date"),
            notes=list(d.get("notes", [])),
        )

    @classmethod
    def from_json_file(cls, path: str) -> "Deal":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    # -- merging in fetched data -----------------------------------------

    def apply_assessor(self, data: dict, source_url: str, when: str) -> List[str]:
        """Fill blanks from an Assessor parcel record. Never overwrites INPUT.

        Returns a list of one-line descriptions of what it filled, so the
        report can show it rather than the user having to diff two objects.
        """
        from .provenance import auto

        filled = []
        mapping = {
            "units": "units",
            "building_sf_assessor": "sqft_main",
            "lot_sf": "sqft_lot",
            "year_built": "year_built",
            "ain": "ain",
            "city": "situs_city",
        }
        for our, theirs in mapping.items():
            cur = getattr(self, our)
            if cur is not None and cur.is_known:
                continue
            val = data.get(theirs)
            if val is None:
                continue
            setattr(self, our, auto(val, source=source_url, checked=when))
            filled.append(f"{our} = {val}")

        if self.seller_assessed_value is None or not self.seller_assessed_value.is_known:
            tot = data.get("current_assessed_total")
            if tot:
                self.seller_assessed_value = auto(
                    tot,
                    source=source_url,
                    checked=when,
                    note=(
                        f"{data.get('current_roll_year')} roll: land "
                        f"{_usd(data.get('current_land_value'))} + improvements "
                        f"{_usd(data.get('current_improvement_value'))}. This is the "
                        f"SELLER's Prop 13 basis, not market value."
                    ),
                )
                filled.append(f"seller_assessed_value = {_usd(tot)}")
        return filled


def _usd(x):
    return "n/a" if x is None else f"${x:,.0f}"
