"""
LA County Assessor — parcel search and parcel detail.

Source: https://portal.assessor.lacounty.gov
Endpoints used (both undocumented; they are what the public portal's own
front end calls, and they return JSON without authentication):

    GET /api/search?search=<free text>          -> [{AIN, SitusStreet, ...}]
    GET /api/parceldetail?ain=<10-digit AIN>    -> {Parcel: {...}}

What this gives us, per parcel, verified against 1223 N Edgemont St on
2026-09-02: AIN, lat/lon, situs address, use code and its decoded meaning,
number of units, year built, effective year, main building square footage,
lot square footage, zoning as carried in the Assessor's property description
database, tax rate area, and the current and prior assessment roll values
with their base years and change reasons.

What it does NOT give us: sale price, sale date, buyer/seller, rent roll,
rentable (as opposed to gross) square footage, or any rent-control status.

Caveats a reader should hold on to:

*   `SqftMain` is the Assessor's building area. It is not net rentable area.
    On the Edgemont test parcel the two differ by about 2,400 sf. Anything
    quoted per square foot must say which square footage it used.
*   `ZoningPDB` is the Assessor's copy of the zoning string, not the City
    Planning system of record. For LA City zoning, ZIMAS is authoritative.
*   Address search is loose. `1223 N Edgemont St` returns 501 matches across
    the whole county, ranked by the portal and not by us, most of them
    sharing only the house number. `find_one` therefore requires an exact
    normalised street match and REFUSES rather than taking the top hit when
    there is none — a tool that silently underwrites the Burbank parcel is
    worse than one that stops. It also refuses when the surviving candidates
    sit in more than one city.
*   The search endpoint returns only AIN, situs street, city, ZIP and legal
    description. It carries NO parcel status, so deleted parcels cannot be
    filtered at search time. Status arrives with the detail record: a parcel
    that was split or merged shows ParcelStatus DELETED with a DeleteDate and
    its successor carries the data. `find_one` fetches details for the
    candidates and prefers ACTIVE ones. On the Edgemont test address this
    matters — AIN 5540011009 is the pre-2018 parcel, deleted, carrying no
    units and no year built, and AIN 5540011015 is the one you want.
*   The portal sits behind a bot-protection layer. It answered plain
    scripted requests when this was written; if that changes the adapter
    fails loudly rather than guessing.
"""

import re
from typing import List, Optional

from ..provenance import Result
from .http import FetchError, fetch_json

BASE = "https://portal.assessor.lacounty.gov"
SEARCH_URL = BASE + "/api/search"
DETAIL_URL = BASE + "/api/parceldetail"

# Assessor use codes: first digit 0 = residential. Second digit gives the form.
# Full code list: https://assessor.lacounty.gov/real-estate-toolkit/property-use-codes
RESIDENTIAL_MULTI_SECOND_DIGITS = {"2", "3", "4", "5"}  # duplex .. 5+ units


def _clean_ain(ain: str) -> str:
    return re.sub(r"[^0-9]", "", ain or "")


def looks_like_ain(text: str) -> bool:
    return len(_clean_ain(text)) == 10 and _clean_ain(text) == text.strip().replace("-", "")


def search_parcels(query: str, **kw) -> Result:
    """Free-text search. Returns Result(data={'matches': [...]}).

    No filtering happens here, because there is nothing to filter on: the
    endpoint returns five fields and parcel status is not one of them.
    """
    url = SEARCH_URL + "?" + "search=" + _urlq(query)
    try:
        raw = fetch_json(url, **kw)
    except FetchError as exc:
        return Result(ok=False, error=str(exc), source_url=SEARCH_URL)

    matches = raw.get("Parcels") or []
    out = []
    for m in matches:
        out.append(
            {
                "ain": m.get("AIN"),
                "situs_street": (m.get("SitusStreet") or "").strip(),
                "situs_city": (m.get("SitusCity") or "").strip(),
                "situs_zip": (m.get("SitusZipCode") or "").strip(),
                "legal": (m.get("LegalDescription") or "").strip(),
            }
        )
    return Result(
        ok=True,
        data={"matches": out, "total_reported": raw.get("TotalCount")},
        source_url=url,
    )


def parcel_detail(ain: str, **kw) -> Result:
    """Full parcel record for one AIN."""
    ain = _clean_ain(ain)
    if len(ain) != 10:
        return Result(ok=False, error=f"AIN must be 10 digits, got {ain!r}")
    url = DETAIL_URL + "?ain=" + ain
    try:
        raw = fetch_json(url, **kw)
    except FetchError as exc:
        return Result(ok=False, error=str(exc), source_url=DETAIL_URL)

    p = raw.get("Parcel")
    if not p:
        return Result(ok=False, error=f"no parcel record for AIN {ain}", source_url=url)

    def num(key):
        v = p.get(key)
        if v in (None, "", " "):
            return None
        try:
            return float(str(v).strip())
        except ValueError:
            return None

    def txt(key):
        v = p.get(key)
        return v.strip() if isinstance(v, str) else v

    year_built = txt("YearBuilt")
    year_built = int(year_built) if year_built and year_built.isdigit() else None

    data = {
        "ain": txt("AIN"),
        "status": txt("ParcelStatus"),
        "delete_date": txt("DeleteDate") or None,
        "latitude": num("Latitude"),
        "longitude": num("Longitude"),
        "situs_street": txt("SitusStreet"),
        "situs_city": txt("SitusCity"),
        "situs_zip": txt("SitusZipCode"),
        "use_code": txt("UseCode"),
        "use_type": txt("UseType"),
        "use_code_meaning": " / ".join(
            x for x in (
                txt("UseCode1stDigit"), txt("UseCode2ndDigit"), txt("UseCode3rdDigit")
            ) if x and x.lower() != "unused or unknown code (no meaning)"
        ),
        "units": int(num("NumOfUnits")) if num("NumOfUnits") else None,
        "year_built": year_built,
        "effective_year": txt("EffectiveYear"),
        "sqft_main": num("SqftMain"),
        "sqft_lot": num("SqftLot"),
        "usable_sqft_lot": num("UsableSqftLot"),
        "beds": num("NumOfBeds"),
        "baths": num("NumOfBaths"),
        "quality_class": txt("QualityClass"),
        "zoning_pdb": txt("ZoningPDB"),
        "tax_rate_area": txt("TaxRateArea"),
        "legal": txt("LegalDescription"),
        # Assessment roll. `current_*` is what is on the roll now; `base_*` is
        # the Prop 13 factored base year value, which is what tells you when
        # the property last changed hands for assessment purposes.
        "current_roll_year": txt("CurrentRoll_BaseYear"),
        "current_land_value": num("CurrentRoll_LandValue"),
        "current_improvement_value": num("CurrentRoll_ImpValue"),
        "current_land_reason": txt("CurrentRoll_LandReasonCodeDetail"),
        "base_value_land": num("BaseValue_Land"),
        "base_value_improvement": num("BaseValue_Imp"),
        "base_value_year": txt("BaseValue_Year"),
        "exemption": txt("Exemption"),
        "district_office": txt("DistrictOffice"),
    }

    cl, ci = data["current_land_value"], data["current_improvement_value"]
    data["current_assessed_total"] = (cl or 0) + (ci or 0) if (cl or ci) else None
    bl, bi = data["base_value_land"], data["base_value_improvement"]
    data["base_value_total"] = (bl or 0) + (bi or 0) if (bl or bi) else None

    return Result(ok=True, data=data, source_url=url)


def find_one(address: str, city_hint: Optional[str] = None, **kw) -> Result:
    """Address -> single parcel detail, or an explicit ambiguity error.

    Refuses to choose when the plausible matches sit in different cities.
    An underwriting tool that silently picks the Burbank parcel when you meant
    the Los Angeles one is worse than a tool that stops.
    """
    if looks_like_ain(address):
        return parcel_detail(address, **kw)

    s = search_parcels(address, **kw)
    if not s.ok:
        return s
    matches: List[dict] = s.data["matches"]
    if not matches:
        return Result(ok=False, error=f"no parcel matched {address!r}", source_url=s.source_url)

    target = _normalise_street(address)
    pool = [m for m in matches if _normalise_street(m["situs_street"]) == target]
    if not pool:
        # The search is loose enough that the top hit is frequently a different
        # street with the same house number. Guessing here would put the whole
        # report on the wrong building, so it stops instead.
        near = "; ".join(
            f"{m['ain']} {m['situs_street']}, {m['situs_city']}" for m in matches[:5]
        )
        return Result(
            ok=False,
            error=(
                f"no parcel whose situs street matches {address!r} exactly "
                f"({len(matches)} loose matches returned). Pass the AIN directly, or "
                f"check the address. Nearest by the portal's own ranking: {near}"
            ),
            source_url=s.source_url,
        )

    if city_hint:
        want = city_hint.strip().upper()
        narrowed = [m for m in pool if want in (m["situs_city"] or "").upper()]
        if narrowed:
            pool = narrowed

    cities = {(m["situs_city"] or "").upper() for m in pool}
    if len(cities) > 1:
        listing = "; ".join(f"{m['ain']} {m['situs_street']}, {m['situs_city']}" for m in pool[:6])
        return Result(
            ok=False,
            error=(
                f"{address!r} matched parcels in more than one city ({', '.join(sorted(cities))}). "
                f"Re-run with --city, or pass the AIN directly. Candidates: {listing}"
            ),
            source_url=s.source_url,
        )

    # Several parcels can share a situs address after a lot split or merge.
    # Prefer the active one; among active ones prefer the one with units on it.
    details = []
    for m in pool[:4]:
        d = parcel_detail(m["ain"], **kw)
        if d.ok:
            details.append(d)
    if not details:
        return Result(ok=False, error=f"found AIN(s) for {address!r} but no detail record loaded")

    active = [d for d in details if (d.data.get("status") or "").upper() == "ACTIVE"]
    if active:
        details = active
    with_units = [d for d in details if d.data.get("units")]
    if with_units:
        details = with_units
    chosen = details[0]
    if len(details) > 1:
        others = ", ".join(d.data["ain"] for d in details[1:])
        chosen.data["sibling_ains"] = others
    return chosen


def _normalise_street(s: str) -> str:
    s = (s or "").upper().strip()
    s = re.sub(r"[.,]", "", s)
    s = re.sub(r"\s+", " ", s)
    # Trailing city/state noise that sometimes rides along on user input.
    s = re.sub(r"\b(LOS ANGELES|CA|CALIFORNIA)\b\s*$", "", s).strip()
    return s


def _urlq(s: str) -> str:
    import urllib.parse

    return urllib.parse.quote(s)
