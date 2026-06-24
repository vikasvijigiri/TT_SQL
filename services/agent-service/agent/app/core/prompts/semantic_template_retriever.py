from typing import List, Dict
from agent.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from agent.app.core.prompts.template_compactor import TemplateCompactor
from agent.app.utils.logger import logger


class SemanticTemplateRetriever:
    """
    Enterprise Domain-Aware Semantic Template Retrieval Engine.
    Routes queries to highly specialized syntax template groups based on domain
    and detected query capabilities. Completely decoupled from specific DB metadata.
    """

    GENOMICS_TEMPLATES = [
        {
            "name": "Nested Array Extraction and Element Classification",
            "tags": ["genomics", "variant", "flatten"],
            "sql": """WITH "expanded" AS (
  SELECT
    r."row_id",
    r."category",
    elem.VALUE:"sample_key"::STRING AS "sample_id",
    elem.VALUE:"values"[0]::INTEGER AS "val0",
    elem.VALUE:"values"[1]::INTEGER AS "val1"
  FROM "TARGET_DB"."TARGET_SCHEMA"."TARGET_TABLE" AS r,
    LATERAL FLATTEN(input => r."nested_array_col") AS elem
  WHERE ARRAY_SIZE(elem.VALUE:"values") >= 1
)
SELECT "sample_id", COUNT(*) AS "match_count"
FROM "expanded"
WHERE "val0" = 1 OR "val1" = 1
GROUP BY "sample_id"
ORDER BY "match_count" DESC;""",
        }
    ]

    ECOMMERCE_TEMPLATES = [
        {
            "name": "Revenue Aggregation with COALESCE and Null-Safe Handling",
            "tags": ["ecommerce", "financial", "aggregation"],
            "sql": """SELECT
  "customer_id",
  COALESCE(SUM("order_total"), 0.0) AS "total_revenue",
  COUNT(DISTINCT "order_id") AS "total_orders"
FROM "TARGET_DB"."TARGET_SCHEMA"."ORDERS"
WHERE "order_status" = 'COMPLETED'
GROUP BY "customer_id"
HAVING COALESCE(SUM("order_total"), 0.0) > 1000.0
ORDER BY "total_revenue" DESC;""",
        }
    ]

    EVENT_STREAM_TEMPLATES = [
        {
            "name": "Clickstream JSON Payload Parsing and Duration Averaging",
            "tags": ["event_stream", "variant", "json"],
            "sql": """SELECT
  ev.VALUE:"event_name"::STRING AS "event_name",
  COUNT(*) AS "total_events",
  AVG(ev.VALUE:"payload"."duration_ms"::INTEGER) AS "avg_duration_ms"
FROM "TARGET_DB"."TARGET_SCHEMA"."LOGS" AS l,
  LATERAL FLATTEN(input => l."raw_event_array") AS ev
WHERE ev.VALUE:"event_name"::STRING = 'CLICK'
GROUP BY "event_name";""",
        }
    ]

    RANKING_TEMPLATES = [
        {
            "name": "Window Deduplication and Top N Ranking with QUALIFY",
            "tags": ["ranking", "windows", "qualify"],
            "sql": """WITH "ranked_items" AS (
  SELECT
    "category_id",
    "item_name",
    "sales_volume",
    ROW_NUMBER() OVER(PARTITION BY "category_id" ORDER BY "sales_volume" DESC) AS rn
  FROM "TARGET_DB"."TARGET_SCHEMA"."ITEMS"
)
SELECT "category_id", "item_name", "sales_volume"
FROM "ranked_items"
WHERE rn <= 5
ORDER BY "category_id", rn;""",
        }
    ]

    ANALYTICS_TEMPLATES = [
        {
            "name": "Standard Date Truncation and Join Analytics",
            "tags": ["analytics", "temporal", "joins"],
            "sql": """SELECT
  DATE_TRUNC('month', u."created_at") AS "signup_month",
  COUNT(DISTINCT u."user_id") AS "new_users"
FROM "TARGET_DB"."TARGET_SCHEMA"."USERS" AS u
INNER JOIN "TARGET_DB"."TARGET_SCHEMA"."SUBSCRIPTIONS" AS s ON u."user_id" = s."user_id"
WHERE s."tier" = 'PREMIUM'
GROUP BY "signup_month"
ORDER BY "signup_month" DESC;""",
        }
    ]

    @classmethod
    def retrieve_templates(
        cls,
        query: str,
        domain: str,
        profile: QueryCapabilityProfile,
        max_templates: int = 2,
    ) -> List[Dict[str, str]]:
        logger.debug(
            f"[SemanticTemplateRetriever] Retrieving templates for domain '{domain}'..."
        )
        selected = []
        d_lower = domain.lower()

        # Domain selection
        if (
            "genom" in d_lower
            or "health" in d_lower
            or any(w in query.lower() for w in ("genotype", "variant", "snp", "allele"))
        ):
            selected.extend(cls.GENOMICS_TEMPLATES)
        elif (
            "e-comm" in d_lower
            or "finan" in d_lower
            or any(w in query.lower() for w in ("order", "revenue", "sales", "price"))
        ):
            selected.extend(cls.ECOMMERCE_TEMPLATES)
        elif any(w in query.lower() for w in ("click", "event", "payload", "log")):
            selected.extend(cls.EVENT_STREAM_TEMPLATES)

        # Capability selection
        if profile.requires_windows or profile.requires_ranking:
            if not any("ranking" in t["tags"] for t in selected):
                selected.extend(cls.RANKING_TEMPLATES)
        if profile.requires_variants or profile.requires_flatten:
            if not any("variant" in t["tags"] for t in selected):
                selected.extend(cls.EVENT_STREAM_TEMPLATES if not selected else [])
        if not selected:
            selected.extend(cls.ANALYTICS_TEMPLATES)

        # Ensure distinct by name
        distinct = []
        seen = set()
        for t in selected:
            if t["name"] not in seen:
                seen.add(t["name"])
                distinct.append(t)

        trimmed = distinct[:max_templates]
        compacted = TemplateCompactor.compact_templates(trimmed)  # type: ignore
        logger.info(
            f"[SemanticTemplateRetriever] Retrieved {len(compacted)} domain-aware templates."
        )
        return compacted
