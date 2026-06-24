from typing import List


def get_geospatial_rules() -> List[str]:
    return [
        "Never apply spatial predicates to BINARY or STRING columns. Wrap first: WKB Ã¢â€ â€™ ST_GEOGRAPHYFROMWKB(col). WKT Ã¢â€ â€™ ST_GEOGRAPHYFROMWKT(col). GeoJSON Ã¢â€ â€™ ST_GEOGRAPHYFROMGEOJSON(col). Apply to both predicate operands. Default SRID: 4326.",
        "ST_DISTANCE (meters), ST_WITHIN, ST_INTERSECTS, ST_DWITHIN (meters), ST_CONTAINS. Never mix GEOGRAPHY and GEOMETRY.",
    ]
