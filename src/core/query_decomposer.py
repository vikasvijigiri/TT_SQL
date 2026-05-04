class QueryDecomposer:
    """
    Decomposes a structured intent into a list of atomic tasks for mapping and planning.
    """

    def decompose(self, intent: dict) -> list[dict]:
        tasks = []

        # Extract filters (pre and post)
        filters = intent.get("filters", [])
        if not filters:
            # Fallback to pre_filters and post_filters if present
            filters = intent.get("pre_filters", []) + intent.get("post_filters", [])

        for f in filters:
            tasks.append({"type": "filter", "value": f})

        # Extract aggregations
        aggregations = intent.get("aggregations", [])
        if not aggregations:
            # Fallback to aggregation_steps if present
            aggregations = intent.get("aggregation_steps", [])

        for agg in aggregations:
            tasks.append({"type": "aggregation", "value": agg})

        return tasks
