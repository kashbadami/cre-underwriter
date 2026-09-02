---
name: cre-underwriter
description: Underwrite an LA-area multifamily property from an address and a rent roll. Fetches the LA County Assessor record, computes price per unit, price per rentable and per building square foot, gross rent multiplier, NOI and cap rate with property taxes reassessed to the purchase price as California does on transfer, and prices the RSO/non-RSO multiplier spread. Determines LA City RSO coverage, Costa-Hawkins vacancy decontrol, AB 1482 applicability, Santa Monica's separate regime and Measure ULA transfer tax, tagging each field with where it came from. Use when asked to underwrite, screen or price an apartment building in Los Angeles or Santa Monica, to check a broker's cap rate, or to work out the rent-control status of an LA address.
---

# LA multifamily underwriting

Address and rent roll in, regulatory overlay and underwriting out.

## The one rule

**Nothing in this tool is allowed to produce a bare number.** Every value in the
output carries a tag saying where it came from:

| Tag | Means |
| --- | --- |
| `auto` | fetched live from a named public source this run |
| `input` | the user supplied it |
| `derived` | computed from other tagged values in the same report |
| `MANUAL` | no public API answers this; a human must look it up, and the URL is given |
| `DEFAULT` | an assumption the tool supplied. Always suspect. |
| `MISSING` | needed, not available, and no default was safe to invent |

When you relay results, **carry the tags through**. A cap rate that came out of a
`DEFAULT` vacancy rate and a floor tax rate is not the same claim as one computed
from a real rent roll and a real Tax Rate Area, and the difference is the whole
value of the tool. Do not smooth over a `MISSING` by supplying a plausible
number of your own — the tool refused on purpose.

## Running it

Requires Python 3.8+. No dependencies, no API keys, nothing to configure.
Everything it fetches is public and unauthenticated.

From an address, with whatever figures are known:

```bash
python3 -m cre_underwriter \
  --address "1223 N Edgemont St" --city "LOS ANGELES" \
  --price 4750000 --rentable-sf 12280 \
  --gross-rent 452381 --opex 96000 \
  --tax-rate 1.25 \
  --format md
```

From a deal file, which is the better path once there is a rent roll:

```bash
python3 -m cre_underwriter --deal path/to/deal.json --format md
```

Useful flags:

- `--check-grm 10.5 --check-cap 6.5` — reconcile against figures someone else
  published. Where the tool can compute the same metric it prints the gap; where
  it cannot, it prints what their figure requires to be true. This is the flag to
  reach for when handed a broker's flyer.
- `--tax-rate` — the total ad valorem rate for the parcel's Tax Rate Area. Without
  it the tool falls back to the 1.0% Prop 13 general levy, which is a **floor** on
  the tax and therefore a **ceiling** on every cap rate in the report. Look the
  rate up at <https://onlineapps.auditor.lacounty.gov/tra/>.
- `--no-fetch` — skip the network entirely.
- `--format md|text|json`, `-o FILE`.
- `--cache-dir DIR` — cache fetched public data so a batch run does not hammer a
  county server.

## The deal file

Only `address` is required. Everything else is optional, and everything absent is
reported as absent rather than assumed.

```json
{
  "address": "1223 N Edgemont St",
  "city": "LOS ANGELES",
  "price": 4750000,
  "rentable_sf": 12280,
  "vacancy_pct": 4.0,
  "operating_expenses_annual": 96000,
  "property_tax_rate_pct": 1.25,
  "direct_assessments_annual": 1800,
  "land_value": 2000000,
  "construction_cost_per_sf": 350,
  "soft_cost_pct": 20,
  "rent_roll": [
    {"unit": "101", "rent_monthly": 2650, "beds": 1, "occupied": true},
    {"unit": "102", "rent_monthly": 2400, "beds": 1, "occupied": false}
  ]
}
```

`operating_expenses_annual` must **exclude** property tax and direct assessments.
The model adds those itself, twice — once on the seller's basis and once
reassessed — and double-counting them silently ruins the cap rate.

Units, building area, lot size, year built, AIN and the seller's assessed value
are fetched from the Assessor and should not be supplied unless overriding.

## What it computes

**Ratios.** Price per unit. Price per rentable square foot *and* per the
Assessor's building square foot — these are different denominators and a flyer
quotes whichever flatters, so the tool prints both and raises a caveat when they
diverge. Gross rent multiplier. Density per acre.

**Cap rate, twice.** California reassesses property to the purchase price on a
change of ownership, so the seller's tax bill is a Prop 13 artefact and says
nothing about what the buyer pays. The tool computes NOI and the cap rate on the
seller's basis, again with taxes reassessed to the price, and reports the delta
in basis points.

Usually reassessment costs the buyer. **Not always** — a property that last traded
above today's price gets a tax cut on transfer and a *higher* cap rate. The tool
reports whichever direction the arithmetic gives. Do not assume the sign.

**The RSO spread in dollars.** The same rent roll valued at the multiple
rent-stabilised stock trades at and at the multiple non-RSO stock trades at, and
the difference between them, so regulatory status visibly moves the valuation.
The two multiples are one practitioner's read of one submarket, recorded as such
in `config/statutes.yaml`. Use them to sanity-check a computed multiplier, never
as an input to a valuation.

**Replacement cost.** Land plus hard cost plus soft cost. There is no public
source for either land at market or construction cost per foot, so the tool will
not invent them: given a land value it prints a grid across hard costs; given a
published replacement figure and no land value it prints every land-and-cost pair
that reproduces it. Somebody who knows the land basis reads their answer off the
table.

**Regulatory overlay.** LA City RSO coverage, Costa-Hawkins vacancy decontrol,
AB 1482 applicability and its current cap, Santa Monica's separate regime with
its dollar-capped adjustment, SB 79, and Measure ULA plus the base city and
county documentary transfer tax.

## What is automatic and what is not

Automatic, from the LA County Assessor's public JSON endpoints: AIN, situs
address, units, year built, building and lot area, use code, zoning as the
Assessor carries it, Tax Rate Area, and the current and base-year assessment roll
values. From those the tool reasons to the RSO, Costa-Hawkins and AB 1482
determinations and computes ULA.

Manual, because no public endpoint answers per parcel — the tool marks the field
`MANUAL` and gives the URL:

- **The authoritative RSO determination.** ZIMAS is a single-page application
  that returns an identical shell for every AIN; LAHD publishes no per-parcel
  endpoint; there is no rent-stabilisation dataset on data.lacity.org. Checked
  2 September 2026. Use <https://zimas.lacity.org/>.
- **Certificate of occupancy date.** The statutory RSO test. The Assessor's year
  built is a proxy and a building dated 1978 cannot be resolved from it at all,
  because the cut-off is 1 October 1978.
- **The parcel's actual tax rate.** LA County publishes rates as PDF and XLSX.
  <https://onlineapps.auditor.lacounty.gov/tra/>
- **Direct assessments**, density-bonus and covenanted affordable restrictions,
  substantial-rehabilitation and luxury exemptions, Santa Monica's coverage
  cut-off, and **SB 79 exposure** — whose constants are flagged unverified in the
  config and which the tool therefore refuses to estimate at all.

**Jurisdiction is inferred from a postal city name**, not a boundary lookup. A
"Los Angeles" mailing address can sit in unincorporated LA County or another
incorporated city, each with a different regime. Every run raises this caveat and
every determination below it depends on it.

## Statutory constants

All in `config/statutes.yaml`, each with its source URL, the date it was checked,
and a `review_after` date. Constants that could not be confirmed against a
primary source are flagged `unverified: true` and the tool refuses to present
them as fetched facts. Stale and unverified sections surface as caveats in the
report automatically — if you see one, say so rather than passing the number on.

## Worked example

`examples/edgemont.json` with `examples/edgemont-vs-palmer.md` runs the tool
against a real January 2026 sale where the outputs are publicly known, and sets
what it produced beside them including where it disagreed. Read that before
trusting anything here on a live deal.
