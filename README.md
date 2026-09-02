# cre-underwriter

Takes an LA-area multifamily address and a rent roll and returns the underwriting
plus the regulatory overlay: price per unit and per foot, gross rent multiplier,
cap rate with property taxes reassessed to the purchase price, replacement cost,
and RSO, Costa-Hawkins, AB 1482, Santa Monica, SB 79 and ULA status. Every number
it prints is tagged with where it came from, and where no public source can
answer it says so and gives you the URL instead of guessing.

Python 3.8+. No dependencies, no API keys, nothing to configure.

## Contents

- [Worked example: 1223 N Edgemont St](#worked-example-1223-n-edgemont-st)
- [What is automated and what is not](#what-is-automated-and-what-is-not)
- [Install](#install)
- [Usage](#usage)
- [What we are unsure about](#what-we-are-unsure-about)

## Worked example: 1223 N Edgemont St

14 units in East Hollywood, sold January 2026 for $4,750,000. Jeffrey Palmer of
PMI Properties published his numbers on this deal, which makes it a test rather
than a demo. Reproduce it with:

```
python3 -m cre_underwriter --deal examples/edgemont.json \
    --check-grm 10.5 --check-cap 6.5 --format md
```

### Side by side

| | Published | This tool | |
| --- | --- | --- | --- |
| Price per unit | $339,000 | $339,286 | agrees |
| Price per sf | $387 | $386.81 | agrees, on the marketed 12,280 sf |
| Gross rent multiplier | ~10.5x | not computed | no rent roll was published |
| Cap rate, taxes reassessed | ~6.5% | not computed | no expense schedule was published |
| Replacement cost | ~$7.3M | not computed | two unknowns behind it, one equation |

Two of five reproduce. Three are refused. The refusals are the honest answer: a
gross rent multiplier without a rent roll and a cap rate without an expense
schedule can only be produced by inventing the inputs, and inventing the inputs
is the failure mode this tool exists to avoid.

What it does instead is invert them, and state what the published figures require
to be true:

- **10.5x on $4,750,000 requires gross scheduled rent of $452,381** — $2,693 per
  unit per month across 14 units.
- **6.5% on $4,750,000 requires NOI of $308,750.**
- **Together they require operating expenses, vacancy and property tax to total
  $143,631, or 31.8% of gross scheduled rent.** At the 1.0% Prop 13 general levy
  the tax is $47,500 of that, leaving $6,866 per unit per year for everything
  else. At a more realistic 1.25% Tax Rate Area total it leaves $6,018. Lean for
  a six-year-old building, but workable. Nothing here contradicts the 6.5%; it
  shows what the figure is standing on.

### Where the tool has something the published figures do not

**1. The tax reassessment runs the wrong way on this deal, in the buyer's
favour.**

The standard warning about California multifamily is that a pro forma copies the
seller's tax bill forward, misses the reassessment to the purchase price, and
overstates the cap rate. Here the Assessor's 2026 roll carries the property at
**$7,176,522** — above the $4,750,000 sale price — so on transfer the tax bill
falls:

| | Assessed value | Tax at 1.0% |
| --- | --- | --- |
| Seller's basis (2026 roll) | $7,176,522 | $71,765 |
| Buyer, reassessed to the price | $4,750,000 | $47,500 |
| | | **−$24,265** |

Reassessment is worth **+51 bps** to the buyer, not a cost. A pro forma carrying
the seller's tax line forward would show about **5.99%** rather than 6.5% —
understating the return. The published 6.5% is stated after reassessment and is
the right one. The point is that a model that only knows "reassessment lowers the
cap rate" gets the sign backwards on this deal.

The seller's basis is a $6,500,000 Prop 13 base year value set in 2021, factored
forward five years at the 2% inflation factor. It matches the current roll to
within 0.0001%:

```
4,225,000 x 1.02^5 = 4,664,741   roll shows 4,664,740
2,275,000 x 1.02^5 = 2,511,784   roll shows 2,511,782
```

So the January 2026 sale had not yet reached the roll when this was fetched
(2 September 2026), and the Assessor's reason code on the land value reads
"Change in Ownership (Transfer)". Read straight: the property last traded at
about **$6.5M in 2021 and $4.75M in January 2026, down roughly 27%**.

**2. This is not an RSO building.**

The Assessor gives the year built as **2019**. LA City RSO covers certificates of
occupancy on or before 1 October 1978, so this sits outside it — and outside
AB 1482 too, which exempts housing certificated within the previous 15 years on a
rolling basis, until roughly **2034**.

That puts the multiplier spread on the other side. On the $452,381 of gross rent
implied by the published 10.5x:

| | Multiple | Value |
| --- | --- | --- |
| At the RSO multiple | 9.0x | $4,071,429 |
| At the non-RSO multiple | 12.0x | $5,428,571 |
| Actual | 10.5x | $4,750,000 |

A non-RSO building traded 12.5% below the 12x convention for non-RSO stock.
Either the convention does not hold in this submarket, or something else is
priced in: deferred maintenance, a covenanted affordable component, an occupancy
problem, or a seller who paid $6.5M in 2021. The tool cannot tell you which. It
can tell you the discount is real and the regulatory explanation is not
available.

One caveat it raises itself: 14 units on an 8,850 sf R3 lot in 2019 is dense
enough to suggest a density bonus, which normally carries covenanted affordable
units with their own restrictions. No source this tool reads can see those. It
marks the field MANUAL rather than assuming the building is unrestricted.

**3. Replacement cost is two unknowns and one equation, so it prints the locus.**

Land at market and construction cost per foot have no public source. Rather than
pick a midpoint, the tool prints every pair that reproduces the published $7.3M
on 14,680 sf with soft costs at 20%:

| If land is worth | then hard cost must be |
| --- | --- |
| $1,000,000 | $358/sf |
| $1,500,000 | $329/sf |
| $2,000,000 | $301/sf |
| $2,500,000 | $272/sf |
| $3,000,000 | $244/sf |
| $4,000,000 | $187/sf |

Anyone who knows the land basis reads their answer off that. Two independently
fetched anchors sit near $7.3M without proving it: the 2026 assessed total of
$7,176,522 (1.7% below) and the 2021 base year value of $6,500,000 (11% below).
At $4.75M the buyer paid 65% of the published replacement estimate and 56% of the
broker's $8.5M.

**4. Two square footages, two different per-foot prices.**

The Assessor carries 14,680 sf of building area against the marketed 12,280 sf of
rentable area — a normal gross-to-net gap of 16.3%. The same sale is $386.81 per
rentable foot and **$323.57 per building foot**. Both correct, different
questions. The tool prints both and raises a caveat, so nobody has to work out
which denominator a flyer used.

Full output: [`examples/edgemont-report.md`](examples/edgemont-report.md).
Longer write-up: [`examples/edgemont-vs-palmer.md`](examples/edgemont-vs-palmer.md).

## What is automated and what is not

Everything fetched is public and unauthenticated. Everything else is named, with
the URL for the check that would resolve it.

### Automated

| Field | Source | Checked |
| --- | --- | --- |
| AIN, situs address, city, ZIP | LA County Assessor, `portal.assessor.lacounty.gov/api/parceldetail` | 2026-09-02 |
| Units, year built, effective year | same | 2026-09-02 |
| Building area (SqftMain), lot area | same | 2026-09-02 |
| Use code and its decoded meaning | same | 2026-09-02 |
| Zoning as the Assessor carries it | same | 2026-09-02 |
| Tax Rate Area number | same | 2026-09-02 |
| Current roll land and improvement values | same | 2026-09-02 |
| Prop 13 base year value and base year | same | 2026-09-02 |
| Latitude and longitude | same | 2026-09-02 |
| LA City RSO coverage — *derived, see below* | statutory date test applied to year built | 2026-09-02 |
| AB 1482 applicability and current cap | `dcba.lacounty.gov/portfolio/rent-increases/` | 2026-09-02 |
| Costa-Hawkins vacancy decontrol | Civ. Code 1954.50 et seq. | 2026-09-02 |
| Santa Monica general adjustment and dollar cap | `santamonica.gov/maximum-lawful-rent` | 2026-09-02 |
| Measure ULA tiers and liability | `finance.lacity.gov/faq/measure-ula` | 2026-09-02 |
| Base city and county documentary transfer tax | `lavote.gov` recorder, transfer taxes | 2026-09-02 |

The Assessor endpoints are undocumented — they are what the public portal's own
front end calls, and they answer without authentication. That makes them more
fragile than a published API, and the adapter fails loudly rather than guessing
if they change.

The three rent-control determinations are tagged **DERIVED, not AUTO**, and the
distinction is deliberate: nothing fetched an RSO status. The tool applied a
statutory date test to a year built that came off an assessment roll. That is a
strong indication, not a determination, and the output says LIKELY COVERED or
LIKELY NOT COVERED and hands over the URL.

### Manual

| Field | Why | Where to check |
| --- | --- | --- |
| Authoritative RSO determination | ZIMAS is a single-page application returning an identical 15,524-byte shell for every AIN; no server-rendered parcel page, no documented service behind it. LAHD publishes no per-parcel endpoint. No rent-stabilisation dataset in the data.lacity.org catalogue. All probed 2026-09-02. | <https://zimas.lacity.org/> |
| Certificate of occupancy date | The actual statutory RSO test. The Assessor's year built is a proxy, and a building dated 1978 cannot be resolved from it at all — the cut-off is 1 October 1978 and the roll carries no month. The tool returns INDETERMINATE for 1978. | ZIMAS, or LADBS records |
| Parcel's total tax rate | LA County publishes Tax Rate Area rates as PDF/XLSX/ZIP, not machine-readable. Without it the tool uses the 1.0% general levy, which is a floor on the tax and a ceiling on every cap rate in the report. | <https://onlineapps.auditor.lacounty.gov/tra/> |
| Direct assessments | Refuse, sewer, lighting, flood control and similar. Not ad valorem, not in any percentage rate, added on top of the bill. Property-specific. | County tax bill for the parcel |
| Density bonus / covenanted affordable units | Not in any source this tool reads, and material on any recent dense infill project. | ZIMAS and LA Housing Department |
| Substantial rehabilitation, luxury and other RSO exemptions | Not checkable from the roll. | LAHD |
| Santa Monica coverage cut-off date | Not carried in this tool's config and not inferred. | <https://www.santamonica.gov/maximum-lawful-rent> |
| SB 79 transit exposure | Requires transit-stop proximity and a local zoning capacity test, neither of which this tool reads — and its constants are flagged unverified in the config. The tool refuses to estimate it. | Statute text |
| Land value at market | The Assessor's land line is a factored Prop 13 base year figure, not market. Substituting it would be wrong by whatever the property has moved since it last traded. | Appraisal or comparable land sales |
| Construction cost per square foot | No public source and no defensible midpoint. The tool prices the range instead. | Local GC bids or a cost service |
| Sale price, sale date, buyer and seller | Not in the Assessor's parcel API. | County Recorder, or a data vendor |
| Rent roll | Never public. | The seller |

**Jurisdiction is inferred from a postal city name, not a boundary lookup.** A
"Los Angeles" mailing address can sit in unincorporated LA County or in another
incorporated city, each with a different rent-control regime. Every run raises
this as a caveat because every determination below it depends on it.

## Install

### As a Claude skill

Copy the directory into your skills folder and start a new session:

```
cp -r cre-underwriter ~/.claude/skills/cre-underwriter
```

`SKILL.md` at the root carries the description Claude matches against, so asking
it to underwrite an LA apartment building, check a broker's cap rate, or work out
the rent-control status of an address will pull it in. Per-project instead of
per-user: put it in `.claude/skills/` inside the project.

### As a plain command line tool

Nothing to install. Clone it and run it:

```
python3 -m cre_underwriter --address "1223 N Edgemont St" --city "LOS ANGELES" --price 4750000
```

### With OpenAI models

**Untested — this describes the shape, not a procedure we have run.** There is no
equivalent of the skills directory to drop this into, so the integration is the
ordinary one for a command line tool:

- Expose `python3 -m cre_underwriter --deal <file> --format json` as a function
  tool. It takes a JSON file path and returns JSON on stdout: `inputs`,
  `metrics`, `scenarios`, `caveats` and `regulatory`, each value carrying its
  `provenance` field.
- Put the contents of `SKILL.md` in the system prompt, or summarise the
  provenance tag table into it. The tags are the reason the output is worth
  anything, and a model that drops them will present a DEFAULT assumption as a
  finding.
- In a sandboxed interpreter, the package is standard library only, so it needs
  no install step — only outbound network access to
  `portal.assessor.lacounty.gov`, or `--no-fetch` if there is none.

If you get this working, the correction is worth having.

## Usage

```
python3 -m cre_underwriter --deal examples/edgemont.json --format md
python3 -m cre_underwriter --address "1223 N Edgemont St" --price 4750000 --units 14
python3 -m cre_underwriter --deal deal.json --check-grm 10.5 --check-cap 6.5
python3 -m cre_underwriter --deal deal.json --no-fetch --format json
```

Flags worth knowing: `--tax-rate` (the parcel's real Tax Rate Area total, without
which every cap rate is an upper bound), `--check-grm` and `--check-cap` (reconcile
against somebody else's published figures), `--no-fetch`, `--cache-dir`,
`--format md|text|json`, `-o FILE`. Full list: `--help`.

A deal file needs only `address`; everything else is optional and everything
absent is reported as absent. `operating_expenses_annual` must **exclude**
property tax and direct assessments — the model adds those itself, twice, once on
the seller's basis and once reassessed.

Tests: `python3 -m unittest discover -s tests`. 72 of them, none touching the
network. They cover the arithmetic with numbers small enough to check on paper,
every branch of the regulatory overlay, the Assessor adapter's address
disambiguation against a stubbed network, the bundled YAML reader against PyYAML
on the real config file, and the documentation — the register, the links, and a
sweep for anything credential-shaped.

## What we are unsure about

Named plainly, because you will find these anyway.

**Measure ULA thresholds.** `finance.lacity.gov` returns HTTP 403 to any scripted
request. The FY 2026-27 tiers in the config ($5.4M at 4%, $10.9M at 5.5%) come
from that page's indexed text, corroborated independently against Hanson Bridgett
and AAGLA. `lavote.gov` has **not** been updated and still shows the FY 2025-26
thresholds of $5.3M and $10.6M. Confirm in a browser before relying on these on a
live deal. This matters for Edgemont specifically: at $4.75M it is $650,000 below
the threshold, and if the threshold is actually $5.3M that headroom is $550,000
instead. Either way no ULA is due, but the margin is not what the tool prints.

**SB 79.** Everything in the config for it is flagged unverified. The exclusion
mechanism recorded there was described by a practitioner and was not confirmed
against the statute text. The tool reports SB 79 as undetermined, raises a
blocking caveat, and the function will refuse to run at all if anyone clears that
flag without rewriting it. Do not price transit upzoning exposure off this.

**The 9x / 12x multiplier spread.** One practitioner's read of one submarket at
one moment — Hollywood RSO moving into the 9x range against 1980s-90s non-RSO
holding near 12x, August 2026. Not a published index. It is a sanity check on a
computed multiplier and nothing more, and the tool says so in the output every
time it uses it.

**The property tax rate.** No LA County .gov page states a typical or average
total rate and the machine-readable files are not machine-readable. The tool uses
the 1.0% Prop 13 general levy as a floor and labels every downstream cap rate an
upper bound. It does not publish a plausible range, because a plausible range
would get used as a number.

**RSO exemptions are not checked.** Government-owned, transient occupancy,
substantial rehabilitation, luxury and others. The tool applies the date test and
the unit count and stops. A pre-1978 building can be outside the RSO for reasons
the roll cannot show.

**Assessor year built is not certificate of occupancy.** They are usually the
same year and sometimes are not. Every determination downstream of a year built
inherits that.

**The Edgemont 2021 transaction is an inference.** The Assessor gives a
$6,500,000 base year value set in 2021 with the reason code "Change in Ownership
(Transfer)", and both land and improvement lines carry the 2021 base year. That
reads as a sale at that price. It is not a recorded sale price — the parcel API
does not carry one — and it has not been checked against the Recorder.

**The Assessor endpoints are undocumented.** They are what the portal's own front
end calls. They answered plain scripted requests on 2 September 2026 and there is
a bot-protection layer in front of them that could start refusing. When that
happens the adapter fails with an error rather than falling back to anything.

## Licence

MIT. See `LICENSE`.
