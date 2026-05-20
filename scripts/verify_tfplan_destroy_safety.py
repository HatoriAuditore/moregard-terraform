#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


VM_ADDRESS_RE = re.compile(r'module\.vms\["([^"]+)"\]\.vsphere_virtual_machine\.this$')


def _extract_vm_name(address: str) -> str | None:
    match = VM_ADDRESS_RE.search(address)
    if match:
        return match.group(1)
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_tfplan_destroy_safety.py <tfplan.json>", file=sys.stderr)
        return 2

    plan_path = Path(sys.argv[1])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    allowed = set(json.loads(os.getenv("ALLOW_DESTROY_VM_NAMES_JSON", "[]")))

    destroy_only: list[tuple[str | None, str]] = []
    replacements: list[tuple[str | None, str, list[str]]] = []
    unknown_destroy_addresses: list[str] = []

    for change in plan.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        if "delete" not in actions:
            continue

        address = change.get("address", "")
        vm_name = _extract_vm_name(address)
        if vm_name is None:
            unknown_destroy_addresses.append(address)
            continue

        if actions == ["delete"]:
            destroy_only.append((vm_name, address))
        else:
            replacements.append((vm_name, address, actions))

    planned_delete_names = {name for name, _ in destroy_only if name}
    replacement_names = {name for name, _, _ in replacements if name}

    errors: list[str] = []
    if unknown_destroy_addresses:
        errors.append(
            "Plan contains destroy actions for unknown resources: "
            + ", ".join(sorted(unknown_destroy_addresses))
        )
    if replacements:
        errors.append(
            "Plan contains replacement actions, not pure deletes: "
            + ", ".join(
                f"{name} ({'/'.join(actions)})"
                for name, _, actions in sorted(replacements)
            )
        )
    if planned_delete_names != allowed:
        errors.append(
            "Plan delete set does not match explicit allow-list. "
            f"Allowed: {', '.join(sorted(allowed)) or '-'}; "
            f"planned: {', '.join(sorted(planned_delete_names | replacement_names)) or '-'}."
        )

    if errors:
        print("Destroy safety check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if planned_delete_names:
        print(
            "Destroy safety check passed for VM(s): "
            + ", ".join(sorted(planned_delete_names))
        )
    else:
        print("Destroy safety check passed: plan does not delete any VMs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
