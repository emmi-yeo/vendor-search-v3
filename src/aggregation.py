def aggregate_vendors(meta: list[dict], filters: dict) -> dict:
    def match(v):
        if filters["industry"]:
            if not any(i.lower() in v["industry"].lower() for i in filters["industry"]):
                return False
        if filters["location"]["country"]:
            if filters["location"]["country"].lower() not in v["country"].lower():
                return False
        if filters["certifications"]:
            if not all(c.lower() in v["certifications"].lower() for c in filters["certifications"]):
                return False
        return True

    filtered = [v for v in meta if match(v)]

    return {
        "count": len(filtered),
        "vendors": filtered[:5]  # sample only
    }
