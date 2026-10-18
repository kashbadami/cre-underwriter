"""
The arithmetic. No network, no config lookups except the GRM spread.

Every metric is a provenance.Value tagged DERIVED, and every metric that could
not be computed is a Value tagged MISSING carrying the name of the input that
was absent. A metric never falls back to a plausible number.

The one piece of this file that is not schoolbook arithmetic is the property
tax treatment, and it is the reason the file exists:

    California reassesses to the purchase price on a change of ownership
    (Rev. & Tax. Code 60-64; BOE change-in-ownership FAQ). The seller's tax
    bill is a Prop 13 artifact of whenever they last bought, adjusted up by
    at most 2% a year. It tells you nothing about what the BUYER will pay.

    A cap rate computed on the seller's tax line is therefore not the buyer's
    cap rate. Most of the time reassessment raises the tax and lowers the cap
    rate. It is not always that direction — a property that last traded higher
    than today's price gets a tax CUT on transfer, which raises the buyer's
    cap rate. This model computes both and reports the delta either way.

Direct assessments (refuse, sewer, lighting, flood control) are not ad valorem
and do not move with the reassessment. They are carried separately, and their
absence is reported rather than assumed to be zero.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .deal import Deal
from .provenance import Caveat, Value, derived, missing


@dataclass
class Underwriting:
    metrics: Dict[str, Value] = field(default_factory=dict)
    caveats: List[Caveat] = field(default_factory=list)
    scenarios: Dict[str, list] = field(default_factory=dict)

    def __getitem__(self, k):
        return self.metrics[k]

    def get(self, k):
        return self.metrics.get(k)

    def known(self, k) -> bool:
        v = self.metrics.get(k)
        return bool(v and v.is_known)

    def num(self, k):
        v = self.metrics.get(k)
        return v.value if v and v.is_known else None


def _f(v: Optional[Value]):
    """The float behind a Value, or None if it is not there."""
    return float(v.value) if v is not None and v.is_known else None


def run(deal: Deal, statutes=None) -> Underwriting:
    m: Dict[str, Value] = {}
    caveats: List[Caveat] = []
    scen: Dict[str, list] = {}

    price = _f(deal.price)
    units = _f(deal.units)
    rsf = _f(deal.rentable_sf)
    bsf = _f(deal.building_sf_assessor)

    # The inputs are carried into the metric table too. A reader should not have
    # to hold the price in their head to check a ratio, and the price itself has
    # a provenance worth showing — it is usually INPUT, i.e. someone told us.
    m["price"] = deal.price
    m["units"] = deal.units

    # -- per-unit and per-foot -------------------------------------------

    m["price_per_unit"] = (
        derived(price / units, note="purchase price / unit count")
        if price and units
        else missing("needs price and units")
    )

    m["price_per_rentable_sf"] = (
        derived(
            price / rsf,
            note="purchase price / net rentable sf as marketed. Compare to the "
            "per-foot figure on the Assessor's building area below; they are "
            "different denominators and brokers quote whichever flatters.",
        )
        if price and rsf
        else missing("needs price and rentable_sf")
    )

    m["price_per_building_sf_assessor"] = (
        derived(price / bsf, note="purchase price / Assessor SqftMain (gross building area)")
        if price and bsf
        else missing("needs price and building_sf_assessor")
    )

    if rsf and bsf and abs(rsf - bsf) / bsf > 0.02:
        caveats.append(
            Caveat(
                "material",
                f"Rentable area ({rsf:,.0f} sf) and the Assessor's building area "
                f"({bsf:,.0f} sf) differ by {abs(bsf - rsf):,.0f} sf "
                f"({abs(bsf - rsf) / bsf * 100:.1f}%). Any $/sf figure must say "
                f"which one it used. ${price / rsf:,.0f}/rentable sf vs "
                f"${price / bsf:,.0f}/building sf here.",
            )
        )

    if units and _f(deal.lot_sf):
        m["units_per_lot_acre"] = derived(
            units / (_f(deal.lot_sf) / 43560.0), note="density as built"
        )

    # -- income ----------------------------------------------------------

    gsr = _f(deal.gross_scheduled_rent_annual)
    other = _f(deal.other_income_annual) or 0.0
    vac_pct = _f(deal.vacancy_pct)

    if gsr:
        m["gross_scheduled_rent_annual"] = deal.gross_scheduled_rent_annual
        m["gross_rent_multiplier"] = derived(
            price / gsr, note="purchase price / annual gross scheduled rent"
        )
        if units:
            m["avg_rent_per_unit_monthly"] = derived(gsr / units / 12.0)
        vac_loss = gsr * (vac_pct or 0.0) / 100.0
        m["vacancy_loss_annual"] = derived(vac_loss, note=f"{vac_pct:g}% of gross scheduled rent")
        egi = gsr + other - vac_loss
        m["effective_gross_income"] = derived(
            egi, note="gross scheduled rent + other income - vacancy loss"
        )
    else:
        egi = None
        for k in (
            "gross_scheduled_rent_annual",
            "gross_rent_multiplier",
            "effective_gross_income",
        ):
            m[k] = missing("needs a rent roll or gross_scheduled_rent_annual")

    # -- property tax, before and after reassessment ---------------------

    rate = _f(deal.property_tax_rate_pct)
    rate_v = deal.property_tax_rate_pct
    if rate is None and statutes is not None:
        floor = statutes.get("property_tax", "general_levy_pct")
        rate = float(floor)
        rate_v = statutes.value("property_tax", "general_levy_pct", "general_levy_source")
        rate_v.note = (
            "Prop 13 general levy ONLY. The real bill is this plus voter-approved "
            "debt service for the parcel's Tax Rate Area, so this is a FLOOR on the "
            "tax and therefore a CEILING on the cap rate. Look up the parcel's TRA "
            "at https://onlineapps.auditor.lacounty.gov/tra/ and pass "
            "--tax-rate to replace it."
        )
        caveats.append(
            Caveat(
                "material",
                "No property tax rate supplied. Used the 1.0% Prop 13 general levy "
                "as a floor. Every cap rate below is therefore an upper bound; the "
                "parcel's actual Tax Rate Area adds voter-approved debt service on "
                "top, and direct assessments on top of that.",
            )
        )

    direct = _f(deal.direct_assessments_annual)
    if direct is None:
        caveats.append(
            Caveat(
                "material",
                "No direct assessments supplied. Refuse, sewer, lighting, flood "
                "control and similar line items are not ad valorem, do not appear "
                "in any percentage rate, and are added to the bill. Treated as zero, "
                "which overstates NOI.",
            )
        )
        direct = 0.0
        m["direct_assessments_annual"] = missing(
            "not supplied; the ad valorem rate does not include them"
        )
    else:
        m["direct_assessments_annual"] = deal.direct_assessments_annual

    if rate is not None and price:
        new_tax = price * rate / 100.0 + direct
        m["property_tax_rate_pct"] = rate_v
        m["property_tax_reassessed_annual"] = derived(
            new_tax,
            note=f"purchase price x {rate:g}% (reassessed to the sale price on "
            f"change of ownership) + ${direct:,.0f} direct assessments",
        )
    else:
        new_tax = None
        m["property_tax_reassessed_annual"] = missing("needs price and a tax rate")

    seller_av = _f(deal.seller_assessed_value)
    if rate is not None and seller_av:
        seller_tax = seller_av * rate / 100.0 + direct
        m["property_tax_sellers_basis_annual"] = derived(
            seller_tax,
            note=f"seller's assessed value ${seller_av:,.0f} x {rate:g}% + direct "
            f"assessments. This is the number on a broker's pro forma.",
        )
        if new_tax is not None:
            m["property_tax_reassessment_delta"] = derived(
                new_tax - seller_tax,
                note="positive = the buyer pays more than the seller did",
            )
    else:
        seller_tax = None
        m["property_tax_sellers_basis_annual"] = missing(
            "needs the seller's assessed value (Assessor current roll)"
        )

    # -- NOI and cap rate -------------------------------------------------

    opex = _f(deal.operating_expenses_annual)
    if egi is not None and opex is not None:
        m["operating_expenses_annual"] = deal.operating_expenses_annual
        m["operating_expense_ratio_pct"] = derived(
            opex / egi * 100.0, note="operating expenses / EGI, EXCLUDING property tax"
        )
        if new_tax is not None:
            noi = egi - opex - new_tax
            m["noi_reassessed"] = derived(
                noi, note="EGI - operating expenses - property tax at the NEW assessed value"
            )
            m["cap_rate_reassessed_pct"] = derived(
                noi / price * 100.0,
                note="THE cap rate. Taxes reset to the purchase price, as California "
                "does on transfer.",
            )
        if seller_tax is not None:
            noi_s = egi - opex - seller_tax
            m["noi_sellers_basis"] = derived(
                noi_s, note="EGI - operating expenses - property tax at the SELLER's basis"
            )
            m["cap_rate_sellers_basis_pct"] = derived(
                noi_s / price * 100.0,
                note="What a pro forma shows when it copies the seller's tax bill "
                "forward. Not the buyer's return.",
            )
        if "cap_rate_reassessed_pct" in m and "cap_rate_sellers_basis_pct" in m:
            d_bps = (
                m["cap_rate_reassessed_pct"].value - m["cap_rate_sellers_basis_pct"].value
            ) * 100.0
            m["cap_rate_reassessment_delta_bps"] = derived(
                d_bps,
                note="negative = reassessment costs the buyer basis points; positive "
                "= the property last traded above today's price and the tax bill falls",
            )
            direction = "costs" if d_bps < 0 else "adds"
            caveats.append(
                Caveat(
                    "material",
                    f"Reassessment {direction} {abs(d_bps):.0f} bps of cap rate "
                    f"({m['cap_rate_sellers_basis_pct'].value:.2f}% on the seller's "
                    f"basis vs {m['cap_rate_reassessed_pct'].value:.2f}% reassessed).",
                )
            )
    else:
        for k in ("noi_reassessed", "cap_rate_reassessed_pct"):
            m[k] = missing("needs income and operating expenses")

    # -- RSO / non-RSO multiplier spread ----------------------------------

    if statutes is not None and gsr:
        rso_grm = float(statutes.get("underwriting", "grm_rso_typical"))
        non_grm = float(statutes.get("underwriting", "grm_non_rso_typical"))
        m["value_at_rso_grm"] = derived(
            gsr * rso_grm,
            note=f"annual gross rent x {rso_grm:g} — the multiple rent-stabilized "
            f"stock trades at",
        )
        m["value_at_non_rso_grm"] = derived(
            gsr * non_grm,
            note=f"annual gross rent x {non_grm:g} — the multiple non-RSO stock trades at",
        )
        m["rso_status_value_spread"] = derived(
            gsr * (non_grm - rso_grm),
            note=f"what regulatory status alone is worth on this rent roll: "
            f"{(non_grm - rso_grm) / non_grm * 100:.0f}% of the non-RSO value",
        )
        caveats.append(
            Caveat(
                "note",
                "The 9x / 12x spread is one practitioner's read of one submarket at "
                "one moment (see config/statutes.yaml, underwriting.grm_source), not "
                "a published index. Use it to sanity-check a computed multiplier, "
                "never as an input to a valuation.",
            )
        )

    # -- replacement cost --------------------------------------------------

    _replacement(deal, m, scen, caveats)

    return Underwriting(metrics=m, caveats=caveats, scenarios=scen)


def _replacement(deal: Deal, m, scen, caveats) -> None:
    """Cost to build the same thing today: land + hard cost + soft cost.

    There is no public API for construction cost. There is no defensible default
    either — LA multifamily hard cost spans a range wide enough that picking a
    midpoint would be inventing the answer. So: if the user supplies a cost per
    foot, this computes one number. If not, it computes a grid, and it solves
    backwards for the cost per foot implied by any comparison figure supplied.
    """
    land = _f(deal.land_value)
    bsf = _f(deal.building_sf_assessor) or _f(deal.rentable_sf)
    soft_pct = _f(deal.soft_cost_pct)
    cost_sf = _f(deal.construction_cost_per_sf)
    price = _f(deal.price)

    if bsf is None:
        m["replacement_cost"] = missing("needs a building area")
        return

    if land is None:
        m["replacement_cost"] = missing(
            "needs land_value. The Assessor's land line is a Prop 13 artifact of the "
            "last transfer, not today's land value, so it is not substituted here."
        )
        caveats.append(
            Caveat(
                "material",
                "No land value supplied, so replacement cost is unpriced. Land is "
                "the input with the widest spread and the one this tool cannot fetch: "
                "the Assessor's land value is a factored base year figure, not market.",
            )
        )

    def total(c_sf, land_val, soft):
        hard = bsf * c_sf
        return land_val + hard * (1.0 + soft / 100.0)

    soft_used = soft_pct if soft_pct is not None else 20.0
    if soft_pct is None:
        caveats.append(
            Caveat(
                "note",
                "Soft costs (design, permits, fees, financing, carry) defaulted to 20% "
                "of hard cost for the replacement grid. Pass soft_cost_pct to replace it.",
            )
        )

    if land is not None and cost_sf is not None:
        m["replacement_cost"] = derived(
            total(cost_sf, land, soft_used),
            note=f"land ${land:,.0f} + {bsf:,.0f} sf x ${cost_sf:,.0f}/sf hard "
            f"+ {soft_used:g}% soft",
        )
        if price:
            m["price_vs_replacement_pct"] = derived(
                price / m["replacement_cost"].value * 100.0,
                note="purchase price as a percentage of cost to build the same thing today",
            )

    if land is not None:
        grid = []
        for c in (250, 300, 350, 400, 450, 500):
            grid.append({"cost_per_sf": c, "replacement_cost": total(c, land, soft_used)})
        scen["replacement_grid"] = grid
        scen["replacement_grid_note"] = (
            f"land ${land:,.0f} + {bsf:,.0f} sf at each hard cost, plus {soft_used:g}% soft costs"
        )

    # Solve backwards from any published replacement figure.
    ref = _f(deal.broker_replacement_estimate)
    if ref and land is not None:
        implied = (ref - land) / (1.0 + soft_used / 100.0) / bsf
        m["broker_replacement_implied_cost_per_sf"] = derived(
            implied,
            note=f"the hard cost per foot that reproduces the ${ref:,.0f} figure "
            f"supplied, given land ${land:,.0f} and {soft_used:g}% soft costs",
        )
    elif ref:
        # Land unknown and cost per foot unknown: one equation, two unknowns.
        # Rather than fix one by assumption, show the locus. Somebody who knows
        # the land basis can read their own answer off it, and a pair that is
        # obviously wrong for the submarket falsifies the published figure.
        locus = []
        for land_try in (1_000_000, 1_500_000, 2_000_000, 2_500_000, 3_000_000, 4_000_000):
            implied = (ref - land_try) / (1.0 + soft_used / 100.0) / bsf
            locus.append({"land_value": land_try, "implied_cost_per_sf": implied})
        scen["replacement_solve_locus"] = locus
        scen["replacement_solve_note"] = (
            f"The ${ref:,.0f} figure supplied has two unknowns behind it — land basis "
            f"and hard cost per foot — and one equation. Every pair below reproduces "
            f"it on {bsf:,.0f} sf with {soft_used:g}% soft costs. The tool will not "
            f"pick one for you."
        )


def invert(price: float, target_grm: float = None, target_cap_pct: float = None) -> dict:
    """What a published headline metric implies about the inputs behind it.

    Brokers and practitioners publish a cap rate and a multiplier and no rent
    roll. Rather than fabricate the rent roll, state what their numbers require:
    an implied gross rent, an implied NOI, and the expense ratio between them.
    If that ratio is implausible, one of the published figures is wrong, and
    that is worth saying out loud.
    """
    out = {}
    if target_grm:
        out["implied_gross_scheduled_rent"] = price / target_grm
    if target_cap_pct:
        out["implied_noi"] = price * target_cap_pct / 100.0
    if target_grm and target_cap_pct:
        gsr = out["implied_gross_scheduled_rent"]
        noi = out["implied_noi"]
        out["implied_total_expense_and_vacancy"] = gsr - noi
        out["implied_total_expense_ratio_pct"] = (gsr - noi) / gsr * 100.0
    return out
