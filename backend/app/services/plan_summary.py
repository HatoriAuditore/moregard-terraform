from __future__ import annotations

import json


def summarize_tfplan_json(raw_plan: str) -> dict[str, int]:
    plan = json.loads(raw_plan)
    summary = {"create": 0, "change": 0, "destroy": 0}

    for change in plan.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        actions_set = set(actions)

        if actions_set == {"create"}:
            summary["create"] += 1
        elif actions_set == {"delete"}:
            summary["destroy"] += 1
        elif actions_set in ({"update"}, {"create", "delete"}):
            summary["change"] += 1
            if actions_set == {"create", "delete"}:
                summary["destroy"] += 0
        elif "update" in actions_set:
            summary["change"] += 1

    return summary
