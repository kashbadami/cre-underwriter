# 1223 N Edgemont St

AIN 5540011015 · built 2019 · sale 2026-01

## Read first

- **SB 79 transit-oriented upzoning: marked unverified in statutes.yaml. The mechanism above is as described in published practitioner commentary, and was NOT independently confirmed against the statute text on 2026-09-02. Marked so it is never presented as verified.**

## Price and size

| Metric | Value | Provenance |
| --- | --- | --- |
| Purchase price | $4,750,000 | input |
| Units | 14 | auto · https://portal.assessor.lacounty.gov/api/parceldetail?ain=5540011015 · checked 2026-09-02 |
| Price per unit | $339,286 | derived |
| Price per rentable sf | $386.81 | derived |
| Price per building sf (Assessor) | $323.57 | derived |
| Units per acre | 68.9 | derived |

- *Price per unit*: purchase price / unit count
- *Price per rentable sf*: purchase price / net rentable sf as marketed. Compare to the per-foot figure on the Assessor's building area below; they are different denominators and brokers quote whichever flatters.
- *Price per building sf (Assessor)*: purchase price / Assessor SqftMain (gross building area)
- *Units per acre*: density as built

## Income

| Metric | Value | Provenance |
| --- | --- | --- |
| Gross scheduled rent (annual) | — | MISSING |
| Gross rent multiplier | — | MISSING |
| Effective gross income | — | MISSING |

- *Gross scheduled rent (annual)*: needs a rent roll or gross_scheduled_rent_annual
- *Gross rent multiplier*: needs a rent roll or gross_scheduled_rent_annual
- *Effective gross income*: needs a rent roll or gross_scheduled_rent_annual

## Expenses and property tax

| Metric | Value | Provenance |
| --- | --- | --- |
| Property tax rate applied | 1.000% | MANUAL · https://auditor.lacounty.gov/faqs/ · checked 2026-09-02 |
| Property tax — seller's basis | $71,765 | derived |
| Property tax — reassessed to price | $47,500 | derived |
| Change in tax on transfer | -$24,265 | derived |
| Direct assessments | — | MISSING |

- *Property tax rate applied*: Prop 13 general levy ONLY. The real bill is this plus voter-approved debt service for the parcel's Tax Rate Area, so this is a FLOOR on the tax and therefore a CEILING on the cap rate. Look up the parcel's TRA at https://onlineapps.auditor.lacounty.gov/tra/ and pass --tax-rate to replace it.
- *Property tax — seller's basis*: seller's assessed value $7,176,522 x 1% + direct assessments. This is the number on a broker's pro forma.
- *Property tax — reassessed to price*: purchase price x 1% (reassessed to the sale price on change of ownership) + $0 direct assessments
- *Change in tax on transfer*: positive = the buyer pays more than the seller did
- *Direct assessments*: not supplied; the ad valorem rate does not include them

## Return

| Metric | Value | Provenance |
| --- | --- | --- |
| NOI, taxes reassessed | — | MISSING |
| Cap rate, taxes reassessed | — | MISSING |

- *NOI, taxes reassessed*: needs income and operating expenses
- *Cap rate, taxes reassessed*: needs income and operating expenses

## Replacement cost

| Metric | Value | Provenance |
| --- | --- | --- |
| Replacement cost | — | MISSING |

- *Replacement cost*: needs land_value. The Assessor's land line is a Prop 13 artefact of the last transfer, not today's land value, so it is not substituted here.

## Regulatory overlay

| Field | Finding | Provenance |
| --- | --- | --- |
| jurisdiction | Los Angeles | derived |
| la city rso status | LIKELY NOT COVERED by the LA City RSO | derived |
| la city rso determination | not fetched | MANUAL · https://zimas.lacity.org/ |
| costa hawkins vacancy decontrol | Yes — statewide | MANUAL · Civ. Code 1954.50 et seq. |
| costa hawkins relevance | Low — post-1978 construction has no stabilised rent to decontrol | derived |
| ab 1482 status | EXEMPT until about 2034 — building is 7 years old | derived |
| sb 79 transit upzoning exposure | not determined | MANUAL · config/statutes.yaml — marked unverified |
| ula transfer tax | $0 | derived |
| base documentary transfer tax | $26,600 | derived |
| ula exemptions | not checked | MANUAL · https://housing.lacity.gov/ula-exemptions |

- *jurisdiction*: From the Assessor's situs city. This is a POSTAL designation. A 'Los Angeles' mailing address can sit in unincorporated LA County or in another incorporated city, and the rent-control regime differs in each. Confirm the incorporated city at https://zimas.lacity.org/ before acting on anything below.
- *la city rso status*: Year built 2019 is after the 1978-10-01 cut-off. Post-1978 construction is outside the RSO. Note this cuts both ways: it also means no vacancy-decontrol upside to buy, because there is no stabilised rent to reset. Replacement units built on a site where RSO units were demolished can carry their own restrictions that a year built will not reveal — confirm at https://zimas.lacity.org/.
- *la city rso determination*: The authoritative status. ZIMAS is a single-page application that returns an identical shell for every AIN, LAHD publishes no per-parcel endpoint, and data.lacity.org carries no rent stabilisation dataset (all checked 2026-09-02). Search the address at https://zimas.lacity.org/, or use the LAHD calculator at https://housing.lacity.gov/rso-rent-increase-calculator.
- *costa hawkins vacancy decontrol*: A stabilised unit resets to market rent on vacancy. This is state law and a city cannot repeal it; statewide repeal was rejected at the ballot in 2018, 2020, 2024. It is what makes turnover, not the allowable annual increase, the engine of value in rent-stabilised stock — and therefore what makes the in-place-to-market rent gap the number to underwrite.
- *costa hawkins relevance*: Vacancy decontrol is only worth something where a rent is held below market by an ordinance. Where it is not, turnover upside is an ordinary market question.
- *ab 1482 status*: AB 1482 exempts housing certificated within the previous 15 years, and the window ROLLS: this building ages into coverage around 2034. Certificate of occupancy issued within the previous 15 years — a ROLLING window, so a building ages into coverage. Civ. Code 1947.12(d) / 1946.2(e)(7). Age here is computed from the Assessor's year built, not the certificate of occupancy.
- *sb 79 transit upzoning exposure*: Requires transit-stop proximity and the local zoning capacity test, neither of which this tool reads. The exclusion mechanism recorded in the config is explicitly flagged unverified: it was described by a practitioner and was NOT confirmed against the statute text. Do not price SB 79 exposure off this tool. Parcel is at 34.09412, -118.29650.
- *ula transfer tax*: $4,750,000 is below the $5,400,000 threshold, so no ULA is due on a transfer at this price. Headroom to the threshold: $650,000.
- *base documentary transfer tax*: City 0.45% + County 0.11% = 0.56% of consideration. Separate from, and additional to, ULA. Source: https://www.lavote.gov/home/recorder/property-document-recording/documentary-transfer-taxes/general-info
- *ula exemptions*: LAMC 21.9.14, administered by LAHD. Qualifying transferees include 501(c)(3) nonprofits, Community Land Trusts and Limited-Equity Housing Cooperatives with an affordable-housing experience requirement, plus government agencies, gifts, transfers where debt equals or exceeds value, bankruptcy, spousal and same-proportion entity transfers. Confidence on this list: medium-high — corroborated across LAHD and Hanson Bridgett; full ordinance text not read

## What the published replacement figure implies

The $7,300,000 figure supplied has two unknowns behind it — land basis and hard cost per foot — and one equation. Every pair below reproduces it on 14,680 sf with 20% soft costs. The tool will not pick one for you.

| If land is worth | then hard cost must be |
| --- | --- |
| $1,000,000 | $358/sf |
| $1,500,000 | $329/sf |
| $2,000,000 | $301/sf |
| $2,500,000 | $272/sf |
| $3,000,000 | $244/sf |
| $4,000,000 | $187/sf |

## Caveats

- **material** — Rentable area (12,280 sf) and the Assessor's building area (14,680 sf) differ by 2,400 sf (16.3%). Any $/sf figure must say which one it used. $387/rentable sf vs $324/building sf here.
- **material** — No property tax rate supplied. Used the 1.0% Prop 13 general levy as a floor. Every cap rate below is therefore an upper bound; the parcel's actual Tax Rate Area adds voter-approved debt service on top, and direct assessments on top of that.
- **material** — No direct assessments supplied. Refuse, sewer, lighting, flood control and similar line items are not ad valorem, do not appear in any percentage rate, and are added to the bill. Treated as zero, which overstates NOI.
- **material** — No land value supplied, so replacement cost is unpriced. Land is the input with the widest spread and the one this tool cannot fetch: the Assessor's land value is a factored base year figure, not market.
- **material** — Jurisdiction is inferred from a postal city name, not from a municipal boundary lookup. Everything in this section depends on it. Confirm the parcel is inside the incorporated city before relying on any determination here.
- **material** — Measure ULA transfer tax (City of Los Angeles): finance.lacity.gov returns HTTP 403 to automated fetch. These figures come from that page's indexed text, corroborated independently by Hanson Bridgett (June 2026) and AAGLA. lavote.gov has NOT been updated and still shows the FY 2025-26 thresholds of $5.3M and $10.6M. CONFIRM IN A BROWSER before relying on these in a live deal.
- **note** — Soft costs (design, permits, fees, financing, carry) defaulted to 20% of hard cost for the replacement grid. Pass soft_cost_pct to replace it.

## Assumptions the tool supplied

Every one of these is a number nobody gave us. Replace them.

- `vacancy_pct` = 5.0 — No vacancy figure supplied. 5% is a convention, not a market observation for this submarket. Supply the actual figure.
- `other_income_annual` = 0.0 — No other income supplied; treated as zero.

## Not computed

- `gross_scheduled_rent_annual` — needs a rent roll or gross_scheduled_rent_annual
- `gross_rent_multiplier` — needs a rent roll or gross_scheduled_rent_annual
- `effective_gross_income` — needs a rent roll or gross_scheduled_rent_annual
- `direct_assessments_annual` — not supplied; the ad valorem rate does not include them
- `noi_reassessed` — needs income and operating expenses
- `cap_rate_reassessed_pct` — needs income and operating expenses
- `replacement_cost` — needs land_value. The Assessor's land line is a Prop 13 artefact of the last transfer, not today's land value, so it is not substituted here.

## Notes on this deal

- The published figures for this deal: $339,000/unit, $387/sf, ~10.5x gross, ~6.5% cap after tax reassessment, replacement cost ~$7.3M against a broker's $8.5M.
- The $8.5M broker replacement figure is recorded here as context but is not used as an input; only the $7.3M figure is passed to the solver.
- Rentable area of 12,280 sf is the marketed figure. The Assessor carries 14,680 sf of building area for this parcel. The report shows both.

## Lookups this run

- LA County Assessor: matched AIN 5540011015 (1223 N EDGEMONT ST, LOS ANGELES CA); filled units = 14, building_sf_assessor = 14680.0, lot_sf = 8850.0, year_built = 2019, ain = 5540011015, seller_assessed_value = $7,176,522

## Reconciliation

- GRM: no rent roll supplied, so nothing to compare. A 10.50x multiple on $4,750,000 requires annual gross scheduled rent of $452,381.
- Cap rate: no expenses supplied, so nothing to compare. A 6.50% cap on $4,750,000 requires NOI of $308,750.
- Taken together they require operating expenses, vacancy and property tax totalling $143,631, which is 31.8% of gross scheduled rent. If that ratio is not plausible for this asset, one of the two published figures is measuring something else.
