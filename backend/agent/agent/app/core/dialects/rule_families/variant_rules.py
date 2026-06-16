from typing import List


def get_variant_rules() -> List[str]:
    return [
        'Access VARIANT object keys using colon notation without single quotes: "col":"key"::TYPE. Nested: "col":"k1"."k2"::TYPE. Alternative: GET_PATH("col", \'key\')::TYPE. Always cast to explicit type. Never use dot notation or single-quoted keys after colon.',
        "A missing VARIANT key returns NULL silently and excludes rows from equality filters. Add IS NULL OR condition when absent-key rows must be included. Document the decision.",
        "Wrap STRING/TEXT columns storing JSON in PARSE_JSON before colon notation. Skip PARSE_JSON if column type is already VARIANT.",
        "Build objects: OBJECT_CONSTRUCT('k', col).",
    ]
