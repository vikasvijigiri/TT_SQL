class QueryDecomposer:
    """
    Decomposes a structured intent into a list of atomic tasks for mapping and planning.
    """

    def decompose(self, intent: dict) -> list[dict]:
        tasks = []

        # 1. Extract Dimensions/Entities
        entities = intent.get("entities", [])
        for ent in entities:
            tasks.append({"type": "entity", "value": ent})

        # 2. Extract Metrics
        metrics = intent.get("metrics", [])
        for met in metrics:
            tasks.append({"type": "metric", "value": met})

        # 3. Extract Filters (pre and post)
        filters = intent.get("filters", [])
        if not filters:
            # Fallback to pre_filters and post_filters if present
            filters = intent.get("pre_filters", []) + intent.get("post_filters", [])

        for f in filters:
            tasks.append({"type": "filter", "value": f})

        # 4. Extract Aggregations
        aggregations = intent.get("aggregations", [])
        if not aggregations:
            # Fallback to aggregation_steps if present
            aggregations = intent.get("aggregation_steps", [])

        for agg in aggregations:
            tasks.append({"type": "aggregation", "value": agg})

        return tasks
