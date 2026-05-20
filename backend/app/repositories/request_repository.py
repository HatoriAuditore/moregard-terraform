from __future__ import annotations

import json
from datetime import UTC, datetime

from app.database import get_connection
from app.models import PipelineLaunchRequest, RequestRecord, RequestStatus, VmDetail, VmSummary
from app.services.terraform_state import list_live_vm_names


def save_request(
    *,
    request_id: str,
    requested_by: str,
    operation: str,
    status: RequestStatus,
    gitlab_project_id: str,
    gitlab_pipeline_id: int | None,
    gitlab_pipeline_url: str | None,
    request_payload: dict,
    terraform_payload: dict,
    pipeline_request: PipelineLaunchRequest,
) -> RequestRecord:
    now = datetime.now(UTC).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO provisioning_requests (
                request_id,
                requested_by,
                operation,
                status,
                gitlab_project_id,
                gitlab_pipeline_id,
                gitlab_pipeline_url,
                request_payload,
                terraform_payload,
                pipeline_request,
                created_at,
                updated_at
            ) VALUES (
                :request_id,
                :requested_by,
                :operation,
                :status,
                :gitlab_project_id,
                :gitlab_pipeline_id,
                :gitlab_pipeline_url,
                :request_payload,
                :terraform_payload,
                :pipeline_request,
                COALESCE((SELECT created_at FROM provisioning_requests WHERE request_id = :request_id), :created_at),
                :updated_at
            )
            """,
            {
                "request_id": request_id,
                "requested_by": requested_by,
                "operation": operation,
                "status": status.value,
                "gitlab_project_id": gitlab_project_id,
                "gitlab_pipeline_id": gitlab_pipeline_id,
                "gitlab_pipeline_url": gitlab_pipeline_url,
                "request_payload": json.dumps(request_payload),
                "terraform_payload": json.dumps(terraform_payload),
                "pipeline_request": json.dumps(pipeline_request.model_dump(mode="json")),
                "created_at": now,
                "updated_at": now,
            },
        )

    return get_request(request_id)


def get_request(request_id: str) -> RequestRecord | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM provisioning_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()

    if row is None:
        return None

    return RequestRecord(
        request_id=row["request_id"],
        requested_by=row["requested_by"],
        operation=row["operation"],
        status=row["status"],
        gitlab_project_id=row["gitlab_project_id"],
        gitlab_pipeline_id=row["gitlab_pipeline_id"],
        gitlab_pipeline_url=row["gitlab_pipeline_url"],
        request_payload=json.loads(row["request_payload"]),
        terraform_payload=json.loads(row["terraform_payload"]),
        pipeline_request=json.loads(row["pipeline_request"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_requests() -> list[RequestRecord]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM provisioning_requests ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()

    return [
        RequestRecord(
            request_id=row["request_id"],
            requested_by=row["requested_by"],
            operation=row["operation"],
            status=row["status"],
            gitlab_project_id=row["gitlab_project_id"],
            gitlab_pipeline_id=row["gitlab_pipeline_id"],
            gitlab_pipeline_url=row["gitlab_pipeline_url"],
            request_payload=json.loads(row["request_payload"]),
            terraform_payload=json.loads(row["terraform_payload"]),
            pipeline_request=json.loads(row["pipeline_request"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def list_vm_summaries() -> list[VmSummary]:
    live_vm_names = list_live_vm_names()
    seen: set[str] = set()
    summaries: list[VmSummary] = []

    for record in list_requests():
        defaults = record.request_payload.get("defaults", {})
        ansible = record.request_payload.get("ansible", {})
        for vm in record.request_payload.get("vms", []):
            name = vm.get("name")
            if not name or name in seen:
                continue
            if live_vm_names is not None and name not in live_vm_names:
                continue

            network = vm.get("network", {})
            hardware = vm.get("hardware", {})
            summaries.append(
                VmSummary(
                    name=name,
                    request_id=record.request_id,
                    request_status=record.status,
                    requested_by=record.requested_by,
                    updated_at=record.updated_at,
                    state_source="terraform_state" if live_vm_names is not None else "request_history",
                    live_present=True if live_vm_names is not None else None,
                    template=vm.get("template"),
                    network=network.get("network"),
                    ipv4_address=network.get("ipv4_address"),
                    domain=network.get("domain") or _fqdn_suffix(defaults, network),
                    cpu=hardware.get("cpu"),
                    ram_mb=hardware.get("ram_mb"),
                    root_disk_gb=hardware.get("root_disk_gb"),
                    ansible_enabled=bool(ansible.get("enabled", False)),
                )
            )
            seen.add(name)

    return summaries


def get_vm_detail(vm_name: str) -> VmDetail | None:
    live_vm_names = list_live_vm_names()
    if live_vm_names is not None and vm_name not in live_vm_names:
        return None

    for record in list_requests():
        defaults = record.request_payload.get("defaults", {})
        ansible = record.request_payload.get("ansible", {})
        for vm in record.request_payload.get("vms", []):
            if vm.get("name") == vm_name:
                return VmDetail(
                    name=vm_name,
                    request_id=record.request_id,
                    request_status=record.status,
                    requested_by=record.requested_by,
                    updated_at=record.updated_at,
                    state_source="terraform_state" if live_vm_names is not None else "request_history",
                    live_present=True if live_vm_names is not None else None,
                    vm=vm,
                    defaults=defaults,
                    ansible=ansible,
                )
    return None


def _fqdn_suffix(defaults: dict, network: dict) -> str | None:
    dns_suffixes = network.get("dns_suffix_list") or []
    if dns_suffixes:
        return dns_suffixes[0]
    return defaults.get("domain")


def update_request_status(
    request_id: str,
    *,
    status: RequestStatus,
    gitlab_pipeline_id: int | None = None,
    gitlab_pipeline_url: str | None = None,
) -> RequestRecord | None:
    now = datetime.now(UTC).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE provisioning_requests
            SET status = :status,
                gitlab_pipeline_id = COALESCE(:gitlab_pipeline_id, gitlab_pipeline_id),
                gitlab_pipeline_url = COALESCE(:gitlab_pipeline_url, gitlab_pipeline_url),
                updated_at = :updated_at
            WHERE request_id = :request_id
            """,
            {
                "request_id": request_id,
                "status": status.value,
                "gitlab_pipeline_id": gitlab_pipeline_id,
                "gitlab_pipeline_url": gitlab_pipeline_url,
                "updated_at": now,
            },
        )

    return get_request(request_id)
