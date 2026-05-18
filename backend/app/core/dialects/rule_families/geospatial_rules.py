from typing import List

def get_geospatial_rules() -> List[str]:
    return [
        "Never apply spatial predicates to BINARY or STRING columns. Wrap first: WKB → ST_GEOGRAPHYFROMWKB(col). WKT → ST_GEOGRAPHYFROMWKT(col). GeoJSON → ST_GEOGRAPHYFROMGEOJSON(col). Apply to both predicate operands. Default SRID: 4326.",
        "ST_DISTANCE (meters), ST_WITHIN, ST_INTERSECTS, ST_DWITHIN (meters), ST_CONTAINS. Never mix GEOGRAPHY and GEOMETRY."
    ]
