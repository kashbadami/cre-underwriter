"""
Command line entry point.

    python3 -m cre_underwriter --address "1223 N Edgemont St" --city "LOS ANGELES" \
        --price 4750000 --rentable-sf 12280

    python3 -m cre_underwriter --deal examples/edgemont.json --format md

Everything the tool fetches is public and unauthenticated. There is no API key
anywhere in this package and nothing to configure.
"""

import argparse
import datetime as dt
import json
import sys

from . import report
from .deal import Deal
from .statutes import Statutes
from .underwriting import invert, run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cre-underwriter",
        description="LA multifamily underwriting with the regulatory overlay, "
        "every number tagged with where it came from.",
    )
    p.add_argument("--deal", help="path to a deal JSON file (see examples/)")
    p.add_argument("--address", help="street address, or a 10-digit AIN")
    p.add_argument("--city", help="city, to disambiguate a street name that repeats")
    p.add_argument("--price", type=float, help="purchase price or asking price")
    p.add_argument("--units", type=int)
    p.add_argument("--rentable-sf", type=float, help="net rentable area as marketed")
    p.add_argument("--gross-rent", type=float, help="annual gross scheduled rent")
    p.add_argument("--opex", type=float, help="annual operating expenses EXCLUDING property tax")
    p.add_argument("--vacancy", type=float, help="vacancy percent")
    p.add_argument(
        "--tax-rate",
        type=float,
        help="total ad valorem rate for the parcel's Tax Rate Area, percent. "
        "Look it up at https://onlineapps.auditor.lacounty.gov/tra/ — without it "
        "the tool uses the 1%% general levy as a floor and says so.",
    )
    p.add_argument("--land-value", type=float)
    p.add_argument("--cost-per-sf", type=float, help="construction hard cost per sf")
    p.add_argument("--soft-cost-pct", type=float)
    p.add_argument("--compare-replacement", type=float,
                   help="a published replacement figure to solve backwards from")
    p.add_argument("--no-fetch", action="store_true", help="skip every network lookup")
    p.add_argument("--timeout", type=int, default=20, help="per-request seconds (default 20)")
    p.add_argument("--cache-dir", help="cache fetched public data here")
    p.add_argument("--format", choices=("md", "text", "json"), default="text")
    p.add_argument("-o", "--out", help="write to a file instead of stdout")
    p.add_argument("--check-grm", type=float, help="a published GRM to reconcile against")
    p.add_argument("--check-cap", type=float, help="a published cap rate percent to reconcile against")
    return p


def deal_from_args(args) -> Deal:
    if args.deal:
        with open(args.deal, "r", encoding="utf-8") as fh:
            d = json.load(fh)
    else:
        d = {}
    cli_map = {
        "address": args.address,
        "city": args.city,
        "price": args.price,
        "units": args.units,
        "rentable_sf": args.rentable_sf,
        "gross_scheduled_rent_annual": args.gross_rent,
        "operating_expenses_annual": args.opex,
        "vacancy_pct": args.vacancy,
        "property_tax_rate_pct": args.tax_rate,
        "land_value": args.land_value,
        "construction_cost_per_sf": args.cost_per_sf,
        "soft_cost_pct": args.soft_cost_pct,
        "broker_replacement_estimate": args.compare_replacement,
    }
    for k, v in cli_map.items():
        if v is not None:
            d[k] = v
    return Deal.from_dict(d)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    deal = deal_from_args(args)

    if not deal.address.is_known and not args.deal:
        print("need --address or --deal", file=sys.stderr)
        return 2

    statutes = Statutes.load()
    today = dt.date.today().isoformat()
    fetch_log = []
    parcel = None

    if not args.no_fetch and deal.address.is_known:
        from .sources import assessor

        kw = {"timeout": args.timeout}
        if args.cache_dir:
            kw["cache_dir"] = args.cache_dir
        city = deal.city.value if deal.city and deal.city.is_known else None
        res = assessor.find_one(str(deal.address.value), city_hint=city, **kw)
        if res.ok:
            parcel = res.data
            filled = deal.apply_assessor(parcel, res.source_url, today)
            fetch_log.append(
                f"LA County Assessor: matched AIN {parcel.get('ain')} "
                f"({parcel.get('situs_street')}, {parcel.get('situs_city')}); "
                f"filled {', '.join(filled) if filled else 'nothing new'}"
            )
        else:
            fetch_log.append(f"LA County Assessor: FAILED — {res.error}")

    uw = run(deal, statutes)

    overlay = None
    try:
        from .regulatory import overlay_for
    except ImportError:
        overlay_for = None
    if overlay_for is not None:
        overlay = overlay_for(
            deal,
            statutes,
            parcel=parcel,
            fetch=not args.no_fetch,
            timeout=args.timeout,
            cache_dir=args.cache_dir,
        )

    if args.format == "json":
        out = report.as_json(deal, uw, overlay)
    else:
        body = (
            report.markdown(deal, uw, overlay)
            if args.format == "md"
            else report.text(deal, uw, overlay)
        )
        extra = []
        if fetch_log:
            extra.append("## Lookups this run" if args.format == "md" else "LOOKUPS THIS RUN")
            extra.append("")
            extra.extend(f"- {x}" for x in fetch_log)
            extra.append("")
        recon = _reconcile(args, deal, uw)
        if recon:
            extra.append("## Reconciliation" if args.format == "md" else "RECONCILIATION")
            extra.append("")
            extra.extend(recon)
            extra.append("")
        out = body + ("\n" + "\n".join(extra) if extra else "")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


def _reconcile(args, deal, uw):
    """Compare published headline figures against what the tool computed, and
    where the tool could not compute one, say what the published figure implies.
    """
    if not (args.check_grm or args.check_cap):
        return []
    price = float(deal.price.value) if deal.price.is_known else None
    if not price:
        return []
    lines = []
    if args.check_grm:
        ours = uw.num("gross_rent_multiplier")
        if ours:
            lines.append(
                f"- GRM: published {args.check_grm:.2f}x, computed {ours:.2f}x "
                f"({(ours - args.check_grm) / args.check_grm * 100:+.1f}%)"
            )
        else:
            lines.append(
                f"- GRM: no rent roll supplied, so nothing to compare. A "
                f"{args.check_grm:.2f}x multiple on ${price:,.0f} requires annual "
                f"gross scheduled rent of ${price / args.check_grm:,.0f}."
            )
    if args.check_cap:
        ours = uw.num("cap_rate_reassessed_pct")
        if ours:
            lines.append(
                f"- Cap rate: published {args.check_cap:.2f}%, computed {ours:.2f}% "
                f"({(ours - args.check_cap) * 100:+.0f} bps)"
            )
        else:
            lines.append(
                f"- Cap rate: no expenses supplied, so nothing to compare. A "
                f"{args.check_cap:.2f}% cap on ${price:,.0f} requires NOI of "
                f"${price * args.check_cap / 100:,.0f}."
            )
    if args.check_grm and args.check_cap:
        inv = invert(price, args.check_grm, args.check_cap)
        lines.append(
            f"- Taken together they require operating expenses, vacancy and property "
            f"tax totalling ${inv['implied_total_expense_and_vacancy']:,.0f}, which is "
            f"{inv['implied_total_expense_ratio_pct']:.1f}% of gross scheduled rent. "
            f"If that ratio is not plausible for this asset, one of the two published "
            f"figures is measuring something else."
        )
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
