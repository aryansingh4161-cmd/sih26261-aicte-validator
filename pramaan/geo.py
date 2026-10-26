"""WK23-18 Geo check (MOCK). Declared latitude/longitude vs a MOCK geocoder lookup of the declared address
(data/mock_issuers/geocoder.json, a table for the demo cities). More than geo_max_km apart (settings, ASSUMPTION) -> X-GEO,
human_review. Annexure-2 2.1 vi. / rules sheet R06 also asks for the satellite-map document; comparing with the coordinates
printed on it is DESIGNED (no such document in the synthetic set). OWNER: Aryan."""
from __future__ import annotations

import json
import os

from .i18n import t
from .photo_check import km
from .schemas import Application, Evidence, Finding


def geocode(address: str, path: str = "data/mock_issuers/geocoder.json") -> dict | None:
    if not address or not os.path.exists(path):
        return None
    return json.load(open(path)).get(address)


def geo_check(app: Application, settings: dict, path: str = "data/mock_issuers/geocoder.json") -> list[Finding]:
    lat, lon, addr = app.declared.get("latitude"), app.declared.get("longitude"), app.declared.get("address")
    hit = geocode(addr, path)
    if hit is None or lat is None or lon is None:
        return []
    d, limit = km((float(lat), float(lon)), (hit["latitude"], hit["longitude"])), float(settings.get("geo_max_km", 2.0))
    if d <= limit:
        return []
    return [Finding(finding_id=f"{app.app_id}-X-GEO-APP", app_id=app.app_id, source="crosscheck", rule_id="X-GEO", severity="medium",
                    confidence=0.8, lane="human_review", title=t("Declared location is far from the address"),
                    reason=t(f"The declared campus location is {d:.1f} km from where the MOCK geocoder places the declared address "
                             f"(limit {limit:g} km, assumption). Check the satellite map and the address."),
                    aph_clause=None, evidence=[Evidence(doc_id=app.app_id, page=1, text=f"declared {lat}, {lon}; geocoded "
                                                                                          f"{hit['latitude']}, {hit['longitude']} (MOCK)")])]
