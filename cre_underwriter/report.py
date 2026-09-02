"""
Rendering. Markdown for reading, JSON for piping into something else.

The formatting rule that matters: a number never appears without its tag. Not
in a summary line, not in a table, not in the headline. If that makes the output
noisier than a broker's one-page flyer, good — the flyer is the thing this is
supposed to be an antidote to.
"""

import json
from typing import Optional

from .provenance import Value

_ORDER = [
    ("Price and size", [
        ("price", "Purchase price", "usd"),
        ("units", "Units", "count"),
        ("price_per_unit", "Price per unit", "usd"),
        ("price_per_rentable_sf", "Price per rentable sf", "usd2"),
        ("price_per_building_sf_assessor", "Price per building sf (Assessor)", "usd2"),
        ("units_per_lot_acre", "Units per acre", "num1"),
    ]),
    ("Income", [
        ("gross_scheduled_rent_annual", "Gross scheduled rent (annual)", "usd"),
        ("avg_rent_per_unit_monthly", "Average rent per unit per month", "usd"),
        ("gross_rent_multiplier", "Gross rent multiplier", "x"),
        ("vacancy_loss_annual", "Vacancy loss", "usd"),
        ("effective_gross_income", "Effective gross income", "usd"),
    ]),
    ("Expenses and property tax", [
        ("operating_expenses_annual", "Operating expenses (ex. property tax)", "usd"),
        ("operating_expense_ratio_pct", "Operating expense ratio", "pct"),
        ("property_tax_rate_pct", "Property tax rate applied", "pct3"),
        ("property_tax_sellers_basis_annual", "Property tax — seller's basis", "usd"),
        ("property_tax_reassessed_annual", "Property tax — reassessed to price", "usd"),
        ("property_tax_reassessment_delta", "Change in tax on transfer", "usd_signed"),
        ("direct_assessments_annual", "Direct assessments", "usd"),
    ]),
    ("Return", [
        ("noi_sellers_basis", "NOI on the seller's tax basis", "usd"),
        ("cap_rate_sellers_basis_pct", "Cap rate on the seller's tax basis", "pct"),
        ("noi_reassessed", "NOI, taxes reassessed", "usd"),
        ("cap_rate_reassessed_pct", "Cap rate, taxes reassessed", "pct"),
        ("cap_rate_reassessment_delta_bps", "Reassessment effect", "bps"),
    ]),
    ("What regulatory status is worth", [
        ("value_at_rso_grm", "Value at the RSO multiple", "usd"),
        ("value_at_non_rso_grm", "Value at the non-RSO multiple", "usd"),
        ("rso_status_value_spread", "Spread attributable to status alone", "usd"),
    ]),
    ("Replacement cost", [
        ("replacement_cost", "Replacement cost", "usd"),
        ("price_vs_replacement_pct", "Price as a share of replacement", "pct"),
        ("broker_replacement_implied_cost_per_sf",
         "Hard cost per sf implied by the figure supplied", "usd"),
    ]),
]


def fmt(v, kind):
    if v is None:
        return "—"
    if kind == "usd":
        return f"${v:,.0f}"
    if kind == "usd2":
        return f"${v:,.2f}"
    if kind == "usd_signed":
        return f"{'+' if v >= 0 else '-'}${abs(v):,.0f}"
    if kind == "pct":
        return f"{v:.2f}%"
    if kind == "pct3":
        return f"{v:.3f}%"
    if kind == "bps":
        return f"{v:+.0f} bps"
    if kind == "x":
        return f"{v:.2f}x"
    if kind == "num1":
        return f"{v:,.1f}"
    if kind == "count":
        return f"{v:,.0f}"
    return str(v)


def _tag_cell(v: Value) -> str:
    if v.tag == "missing":
        return "MISSING"
    bits = [v.label()]
    return bits[0]


def markdown(deal, uw, overlay=None, title=None) -> str:
    L = []
    addr = deal.address.value if deal.address.is_known else "unknown address"
    L.append(f"# {title or addr}")
    L.append("")
    ain = deal.ain.value if deal.ain and deal.ain.is_known else None
    sub = []
    if ain:
        sub.append(f"AIN {ain}")
    if deal.year_built and deal.year_built.is_known:
        sub.append(f"built {deal.year_built.value}")
    if deal.sale_date and deal.sale_date.is_known:
        sub.append(f"sale {deal.sale_date.value}")
    if sub:
        L.append(" · ".join(sub))
        L.append("")

    blocking = [c for c in uw.caveats if c.severity == "blocking"]
    if overlay:
        blocking += [c for c in overlay.caveats if c.severity == "blocking"]
    if blocking:
        L.append("## Read first")
        L.append("")
        for c in blocking:
            L.append(f"- **{c.text}**")
        L.append("")

    for heading, rows in _ORDER:
        present = [(k, lbl, kind) for k, lbl, kind in rows if k in uw.metrics]
        if not present:
            continue
        L.append(f"## {heading}")
        L.append("")
        L.append("| Metric | Value | Provenance |")
        L.append("| --- | --- | --- |")
        for k, lbl, kind in present:
            v = uw.metrics[k]
            val = fmt(v.value, kind) if v.is_known else "—"
            L.append(f"| {lbl} | {val} | {_tag_cell(v)} |")
        L.append("")
        notes = [
            (lbl, uw.metrics[k].note)
            for k, lbl, _ in present
            if uw.metrics[k].note
        ]
        for lbl, note in notes:
            L.append(f"- *{lbl}*: {note}")
        if notes:
            L.append("")

    if overlay is not None:
        L.append(overlay.to_markdown())

    grid = uw.scenarios.get("replacement_grid")
    if grid:
        L.append("## Replacement cost at a range of hard costs")
        L.append("")
        L.append(f"{uw.scenarios.get('replacement_grid_note', '')}")
        L.append("")
        L.append("| Hard cost $/sf | Replacement cost |")
        L.append("| --- | --- |")
        for row in grid:
            L.append(f"| ${row['cost_per_sf']:,.0f} | ${row['replacement_cost']:,.0f} |")
        L.append("")
        L.append(
            "There is no public source for construction cost per foot and no "
            "defensible midpoint, so the tool prices the range rather than "
            "picking a number. Supply `construction_cost_per_sf` for a single figure."
        )
        L.append("")

    locus = uw.scenarios.get("replacement_solve_locus")
    if locus:
        L.append("## What the published replacement figure implies")
        L.append("")
        L.append(uw.scenarios.get("replacement_solve_note", ""))
        L.append("")
        L.append("| If land is worth | then hard cost must be |")
        L.append("| --- | --- |")
        for row in locus:
            L.append(
                f"| ${row['land_value']:,.0f} | ${row['implied_cost_per_sf']:,.0f}/sf |"
            )
        L.append("")

    others = [c for c in uw.caveats if c.severity != "blocking"]
    if overlay:
        others += [c for c in overlay.caveats if c.severity != "blocking"]
    if others:
        L.append("## Caveats")
        L.append("")
        for c in sorted(others, key=lambda c: 0 if c.severity == "material" else 1):
            L.append(f"- **{c.severity}** — {c.text}")
        L.append("")

    assumptions = [
        (k, v) for k, v in uw.metrics.items() if v.is_assumption and v.tag == "default"
    ]
    for name in ("vacancy_pct", "other_income_annual"):
        v = getattr(deal, name, None)
        if v is not None and v.tag == "default":
            assumptions.append((name, v))
    if assumptions:
        L.append("## Assumptions the tool supplied")
        L.append("")
        L.append("Every one of these is a number nobody gave us. Replace them.")
        L.append("")
        for k, v in assumptions:
            L.append(f"- `{k}` = {v.value} — {v.note}")
        L.append("")

    miss = [(k, v) for k, v in uw.metrics.items() if v.tag == "missing"]
    if miss:
        L.append("## Not computed")
        L.append("")
        for k, v in miss:
            L.append(f"- `{k}` — {v.note}")
        L.append("")

    if deal.notes:
        L.append("## Notes on this deal")
        L.append("")
        for n in deal.notes:
            L.append(f"- {n}")
        L.append("")

    return "\n".join(L).rstrip() + "\n"


def as_json(deal, uw, overlay=None) -> str:
    out = {
        "inputs": {
            k: v.as_dict()
            for k, v in vars(deal).items()
            if isinstance(v, Value)
        },
        "metrics": {k: v.as_dict() for k, v in uw.metrics.items()},
        "scenarios": uw.scenarios,
        "caveats": [{"severity": c.severity, "text": c.text} for c in uw.caveats],
    }
    if overlay is not None:
        out["regulatory"] = overlay.as_dict()
    return json.dumps(out, indent=2, default=str)


def text(deal, uw, overlay=None) -> str:
    """Markdown minus the table pipes, for a terminal."""
    md = markdown(deal, uw, overlay)
    lines = []
    for line in md.splitlines():
        if line.startswith("| --- "):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            lines.append(f"  {cells[0]:<42} {cells[1]:>16}   {cells[2] if len(cells) > 2 else ''}")
        elif line.startswith("#"):
            lines.append("")
            lines.append(line.lstrip("# ").upper())
            lines.append("-" * len(line.lstrip("# ")))
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"
