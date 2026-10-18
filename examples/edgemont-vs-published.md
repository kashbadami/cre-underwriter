# 1223 N Edgemont St — published figures against the tool's output

A local broker published five figures for the January 2026 sale
of this 14-unit East Hollywood building at $4,750,000. This is what the tool
produces from the same starting facts, and where it does not agree, why.

Reproduce it with:

```
python3 -m cre_underwriter --deal examples/edgemont.json \
    --check-grm 10.5 --check-cap 6.5 --format md
```

Full output: [`edgemont-report.md`](edgemont-report.md).

## Side by side

| | Published | This tool | |
| --- | --- | --- | --- |
| Price per unit | $339,000 | $339,286 | agrees |
| Price per sf | $387 | $386.81 | agrees, on the marketed 12,280 sf |
| Gross rent multiplier | ~10.5x | not computed | no rent roll was published |
| Cap rate, taxes reassessed | ~6.5% | not computed | no expense schedule was published |
| Replacement cost | ~$7.3M | not computed | needs a land basis and a hard cost per foot |

Two of the five reproduce. The other three the tool refuses, and the refusals are
the honest answer: a gross rent multiplier without a rent roll and a cap rate
without an expense schedule can only be produced by inventing the inputs.

What the tool does instead is invert them — state what the published figures
require to be true — and that turns out to be the more useful output.

## 1. Price per unit and price per foot: agree

$4,750,000 / 14 = $339,286. $4,750,000 / 12,280 sf = $386.81. Both round to his
figures. Unit count comes from the Assessor (AIN 5540011015), not from us.

One thing worth flagging, which is a caveat in the tool's output and not a
disagreement: the Assessor carries **14,680 sf** of building area for this
parcel against the marketed 12,280 sf of rentable area — a 2,400 sf, 16.3%
gap, which is a normal gross-to-net difference. On the Assessor's denominator
the same sale is **$323.57/sf**. Both are correct; they answer different
questions. The tool prints both so nobody has to guess which one a flyer used.

## 2. Gross rent multiplier: not reproduced, inverted instead

At 10.5x on $4,750,000 the annual gross scheduled rent must be **$452,381** —
$37,698 a month, or **$2,693 per unit per month** across 14 units.

The tool does not know whether that is the actual rent roll. It states the
requirement and stops.

## 3. Cap rate: not reproduced, and the reassessment goes the unexpected way

At 6.5% on $4,750,000, NOI must be **$308,750**.

Taken with the 10.5x multiplier, the two published figures together require
operating expenses, vacancy and property tax to total **$143,631 — 31.8% of
gross scheduled rent**. That is a workable load for a 2019-built building, but
it is tight once the tax is carried:

| Tax rate assumed | Property tax | Everything else | Per unit per year |
| --- | --- | --- | --- |
| 1.000% (Prop 13 general levy — a floor) | $47,500 | $96,131 | $6,866 |
| 1.250% (a plausible Tax Rate Area total) | $59,375 | $84,256 | $6,018 |

$6,000–6,900 per unit per year for management, insurance, utilities, repairs,
reserves and vacancy is lean but not unreasonable on a six-year-old building.
Nothing here contradicts his 6.5%; it just shows what it is standing on.

**The finding worth his time is the direction of the tax reassessment.**

The standard warning about California multifamily is that a naive model copies
the seller's tax bill forward, misses the reassessment to the purchase price,
and overstates the buyer's cap rate. On this parcel it runs the other way.

The Assessor's 2026 roll carries this property at **$7,176,522** — land
$4,664,740 plus improvements $2,511,782. That is *above* the $4,750,000 sale
price. So on transfer the tax bill **falls**:

| | Assessed value | Tax at 1.0% |
| --- | --- | --- |
| Seller's basis (2026 roll) | $7,176,522 | $71,765 |
| Buyer, reassessed to the price | $4,750,000 | $47,500 |
| | | **−$24,265** |

Reassessment is worth **+51 bps** to the buyer here, not a cost. A model that
carried the seller's tax line forward would show roughly **5.99%**, not 6.5% —
understating the return rather than overstating it. The published 6.5% is stated
after reassessment and is the correct one; the point is that the usual
adjustment has the opposite sign on this deal, and a tool that only knows the
rule of thumb "reassessment lowers the cap rate" gets it backwards.

**Where the seller's basis came from.** The parcel's Prop 13 base year value is
$6,500,000, set in 2021 — land $4,225,000, improvements $2,275,000. The 2026
roll figures are those base values factored forward at the 2% annual Prop 13
inflation factor for five years, and they match to within 0.0001%:

```
4,225,000 x 1.02^5 = 4,664,741   roll shows 4,664,740
2,275,000 x 1.02^5 = 2,511,784   roll shows 2,511,782
```

That is worth stating explicitly, because it means the January 2026 sale had not
yet reached the roll when this was fetched (2 September 2026), and it means the
2021 base was itself set by a change of ownership — the Assessor's reason code
on the current land value reads "Change in Ownership (Transfer)". Read straight,
the property last traded at about **$6.5M in 2021 and at $4.75M in January 2026:
down roughly 27%.**

## 4. Replacement cost: not reproduced, because it has two unknowns

The published ~$7.3M against a broker's $8.5M. Replacement cost is land plus hard
cost plus soft cost, and the tool has no public source for either land value at
market or construction cost per foot. It will not invent them.

What it does is show the locus — every land-and-hard-cost pair that reproduces
$7.3M on 14,680 sf with soft costs at 20%:

| If land is worth | then hard cost must be |
| --- | --- |
| $1,000,000 | $358/sf |
| $1,500,000 | $329/sf |
| $2,000,000 | $301/sf |
| $2,500,000 | $272/sf |
| $3,000,000 | $244/sf |
| $4,000,000 | $187/sf |

Anyone who knows the land basis reads their answer off that table. A pair that
is obviously wrong for East Hollywood falsifies the $7.3M.

Two independently fetched anchors sit close to his figure, which is not proof
but is worth noting:

- the 2026 assessed total is **$7,176,522**, 1.7% below $7.3M;
- the 2021 base year value — apparently a real transaction price — is
  **$6,500,000**, 11% below it.

At $4.75M the buyer paid **65% of his replacement estimate**, and 56% of the
broker's $8.5M.

## 5. The finding that is not in his published figures: this is not an RSO building

The Assessor gives the year built as **2019**. LA City RSO covers buildings with
a certificate of occupancy on or before **1 October 1978**, so on that date this
property is **outside** the RSO — and it is also outside AB 1482, which exempts
housing certificated within the previous 15 years on a rolling basis, so this
building does not age into state coverage until roughly **2034**.

That matters to the valuation, because the multiplier spread runs the other way
from what a 1920s East Hollywood address would suggest. On the $452,381 of gross
rent implied by his own 10.5x:

| | Multiple | Value |
| --- | --- | --- |
| At the RSO multiple | 9.0x | $4,071,429 |
| At the non-RSO multiple | 12.0x | $5,428,571 |
| Actual | 10.5x | $4,750,000 |

A non-RSO 14-unit building traded at 10.5x, **12.5% below** the 12x convention
for non-RSO stock and only 17% above where rent-stabilised stock trades. Either
the convention does not hold in this submarket, or something else is priced into
this deal — deferred maintenance, a covenanted affordable component, an occupancy
problem, or a motivated seller who bought at $6.5M in 2021. The tool cannot tell
you which. It can tell you the discount is real and that the regulatory
explanation is not available.

**The 9x/12x spread is the broker's own read of one submarket at one moment** — it is
recorded as such in `config/statutes.yaml` and it is not a published index. It is
used above as a sanity check, which is the only thing it is good for.

**Caveat on the 2019 build date.** A 14-unit building on an 8,850 sf R3 lot in
2019 is dense enough to suggest a density bonus, and a density bonus normally
carries covenanted affordable units with their own rent restrictions. Those
covenants are not in any of the sources this tool reads. Verifying that requires
ZIMAS and the LA Housing Department, by hand — the tool marks it MANUAL rather
than assuming the building is unrestricted.

## What this example is meant to demonstrate

Two of five figures reproduce exactly. Three are refused. The refusals produce
better information than a guess would have: the rent roll the multiplier
requires, the expense load the cap rate requires, and the land-and-cost pairs
the replacement figure requires.

And the one place the tool has something the published figures do not is a
consequence of it reading the Assessor's roll rather than a broker's flyer —
that the reassessment on this deal is a **tax cut worth 51 bps**, not the usual
cost, and that the building is **outside the RSO**, which moves it to the wrong
side of a spread he uses himself.
