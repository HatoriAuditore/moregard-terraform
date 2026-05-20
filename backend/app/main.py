from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.config import settings
from app.database import init_db
from app.models import (
    AnsibleRunRequest,
    AnsibleRunResult,
    ApplyRequest,
    OperationType,
    PipelineLaunchResult,
    PipelineLaunchRequest,
    PipelineStatusResponse,
    ProvisionRequest,
    RequestRecord,
    RequestStatus,
    VmDetail,
    VmSummary,
)
from app.repositories.request_repository import (
    get_request,
    get_vm_detail,
    list_requests,
    list_vm_summaries,
    save_request,
    update_request_status,
)
from app.services.gitlab import GitLabClientError, create_pipeline, create_pipeline_for_project, get_pipeline
from app.services.gitlab import get_job_artifact_text, get_pipeline_jobs, get_project, play_job
from app.services.plan_summary import summarize_tfplan_json
from app.services.pipeline import (
    build_ansible_only_launch_request,
    build_inventory_sync_vm_payload,
    build_pipeline_launch_request,
)
from app.services.request_status import map_pipeline_status_to_request_status
from app.services.terraform_payload import build_terraform_payload
from app.services.terraform_state import get_live_vm_diagnostics


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def healthcheck() -> dict:
    checks: dict[str, dict[str, object]] = {
        "backend_api": {"status": "ok", "message": "Backend API is responding."}
    }

    state = get_live_vm_diagnostics()
    checks["terraform_state_access"] = {
        "status": "ok" if state["status"] == "ok" else "error",
        "message": state["message"],
    }
    checks["live_vms_visible"] = {
        "status": "ok" if state["status"] == "ok" else "error",
        "count": state["count"],
        "message": f"{state['count']} live VM(s) visible from Terraform state." if state["status"] == "ok" else state["message"],
    }

    try:
        terraform_project = get_project(settings.gitlab_project_id)
        checks["gitlab_api"] = {
            "status": "ok",
            "message": "GitLab API is reachable.",
            "project": terraform_project.get("path_with_namespace", settings.gitlab_project_id),
        }
    except GitLabClientError as exc:
        checks["gitlab_api"] = {
            "status": "error",
            "message": str(exc),
            "project": settings.gitlab_project_id,
        }

    if settings.ansible_project_path:
        try:
            ansible_project = get_project(settings.ansible_project_path)
            checks["ansible_project_trigger"] = {
                "status": "ok",
                "message": "Ansible GitLab project is reachable.",
                "project": ansible_project.get("path_with_namespace", settings.ansible_project_path),
            }
        except GitLabClientError as exc:
            checks["ansible_project_trigger"] = {
                "status": "error",
                "message": str(exc),
                "project": settings.ansible_project_path,
            }
    else:
        checks["ansible_project_trigger"] = {
            "status": "skipped",
            "message": "Ansible project path is not configured.",
        }

    overall = "ok"
    if any(check["status"] == "error" for check in checks.values()):
        overall = "degraded"

    return {"status": overall, "environment": settings.env, "checks": checks}


@app.post("/api/v1/provisioning/payload")
def preview_payload(request: ProvisionRequest) -> dict:
    terraform_payload = build_terraform_payload(request)
    pipeline_request = build_pipeline_launch_request(request)
    return {
        "status": RequestStatus.requested,
        "terraform_payload": terraform_payload.model_dump(mode="json"),
        "pipeline_request": pipeline_request.model_dump(mode="json"),
    }


@app.post("/api/v1/provisioning/requests", response_model=PipelineLaunchResult)
def create_request(request: ProvisionRequest) -> PipelineLaunchResult:
    terraform_payload = build_terraform_payload(request)
    pipeline_request = build_pipeline_launch_request(request)
    initial_status = RequestStatus.requested
    status = RequestStatus.planned if request.operation.value == "plan" else RequestStatus.apply_pending

    save_request(
        request_id=request.request_id,
        requested_by=request.requested_by,
        operation=request.operation.value,
        status=initial_status,
        gitlab_project_id=settings.gitlab_project_id,
        gitlab_pipeline_id=None,
        gitlab_pipeline_url=None,
        request_payload=request.model_dump(mode="json"),
        terraform_payload=terraform_payload.model_dump(mode="json"),
        pipeline_request=pipeline_request,
    )

    try:
        pipeline_response = create_pipeline(pipeline_request)
    except GitLabClientError as exc:
        failed_record = update_request_status(
            request.request_id,
            status=RequestStatus.failed,
        )
        raise HTTPException(status_code=502, detail={"message": str(exc), "request": failed_record.model_dump(mode="json")}) from exc

    record = save_request(
        request_id=request.request_id,
        requested_by=request.requested_by,
        operation=request.operation.value,
        status=status,
        gitlab_project_id=settings.gitlab_project_id,
        gitlab_pipeline_id=pipeline_response.get("id"),
        gitlab_pipeline_url=pipeline_response.get("web_url"),
        request_payload=request.model_dump(mode="json"),
        terraform_payload=terraform_payload.model_dump(mode="json"),
        pipeline_request=pipeline_request,
    )

    return PipelineLaunchResult(
        request_id=record.request_id,
        status=record.status,
        operation=request.operation,
        terraform_payload=terraform_payload,
        pipeline_request=pipeline_request,
        pipeline_id=record.gitlab_pipeline_id,
        pipeline_web_url=record.gitlab_pipeline_url,
    )


@app.get("/api/v1/provisioning/requests/{request_id}", response_model=RequestRecord)
def get_request_status(request_id: str) -> RequestRecord:
    record = get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' was not found.")
    return record


@app.get("/api/v1/provisioning/requests", response_model=list[RequestRecord])
def get_requests() -> list[RequestRecord]:
    return list_requests()


@app.get("/api/v1/vms", response_model=list[VmSummary])
def get_vms() -> list[VmSummary]:
    return list_vm_summaries()


@app.get("/api/v1/vms/{vm_name}", response_model=VmDetail)
def get_vm(vm_name: str) -> VmDetail:
    record = get_vm_detail(vm_name)
    if record is None:
        raise HTTPException(status_code=404, detail=f"VM '{vm_name}' was not found.")
    return record


@app.get("/api/v1/provisioning/requests/{request_id}/pipeline", response_model=PipelineStatusResponse)
def get_pipeline_status(request_id: str) -> PipelineStatusResponse:
    record = get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' was not found.")
    if record.gitlab_pipeline_id is None:
        raise HTTPException(status_code=409, detail=f"Request '{request_id}' does not have a GitLab pipeline yet.")

    try:
        pipeline = get_pipeline(record.gitlab_pipeline_id)
        jobs = get_pipeline_jobs(record.gitlab_pipeline_id)
    except GitLabClientError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc), "request_id": request_id}) from exc

    apply_job = next((job for job in jobs if job.get("name") == "apply"), None)
    apply_job_status = apply_job.get("status") if apply_job else None
    apply_available = apply_job_status == "manual"

    plan_summary = None
    plan_job = next((job for job in jobs if job.get("name") == "plan" and job.get("status") == "success"), None)
    if plan_job is not None:
        try:
            plan_summary = summarize_tfplan_json(get_job_artifact_text(plan_job["id"], "tfplan.json"))
        except GitLabClientError:
            plan_summary = None

    refreshed_status = map_pipeline_status_to_request_status(
        operation=record.operation,
        pipeline_status=pipeline["status"],
        ansible_enabled=bool(record.request_payload.get("ansible", {}).get("enabled", False)),
    )
    refreshed_record = update_request_status(
        request_id,
        status=refreshed_status,
        gitlab_pipeline_id=pipeline.get("id"),
        gitlab_pipeline_url=pipeline.get("web_url"),
    )

    return PipelineStatusResponse(
        request_id=request_id,
        pipeline_id=pipeline["id"],
        pipeline_status=pipeline["status"],
        pipeline_web_url=pipeline.get("web_url"),
        request_status=refreshed_record.status if refreshed_record else refreshed_status,
        apply_job_status=apply_job_status,
        apply_available=apply_available,
        plan_summary=plan_summary,
    )


@app.post("/api/v1/provisioning/requests/{request_id}/apply", response_model=PipelineLaunchResult)
def apply_request(request_id: str, apply_request: ApplyRequest) -> PipelineLaunchResult:
    record = get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' was not found.")
    if record.gitlab_pipeline_id is None:
        raise HTTPException(status_code=409, detail=f"Request '{request_id}' does not have a GitLab pipeline yet.")
    if record.status in {RequestStatus.applied, RequestStatus.configured}:
        raise HTTPException(status_code=409, detail=f"Request '{request_id}' has already been applied.")
    if record.status == RequestStatus.failed:
        raise HTTPException(status_code=409, detail=f"Request '{request_id}' is in failed state and cannot be applied.")

    try:
        jobs = get_pipeline_jobs(record.gitlab_pipeline_id)
        apply_job = next((job for job in jobs if job.get("name") == "apply"), None)
        if apply_job is None:
            raise HTTPException(status_code=409, detail=f"Request '{request_id}' does not have an apply job in its pipeline.")
        if apply_job.get("status") == "success":
            raise HTTPException(status_code=409, detail=f"Request '{request_id}' has already been applied.")
        if apply_job.get("status") != "manual":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Request '{request_id}' cannot be applied right now because apply job status is "
                    f"'{apply_job.get('status')}'."
                ),
            )
        played_job = play_job(apply_job["id"])
    except GitLabClientError as exc:
        failed_record = update_request_status(request_id, status=RequestStatus.failed)
        raise HTTPException(status_code=502, detail={"message": str(exc), "request": failed_record.model_dump(mode="json") if failed_record else request_id}) from exc

    updated_record = save_request(
        request_id=record.request_id,
        requested_by=apply_request.requested_by,
        operation=OperationType.apply.value,
        status=RequestStatus.apply_pending,
        gitlab_project_id=settings.gitlab_project_id,
        gitlab_pipeline_id=record.gitlab_pipeline_id,
        gitlab_pipeline_url=record.gitlab_pipeline_url,
        request_payload=record.request_payload,
        terraform_payload=record.terraform_payload,
        pipeline_request=PipelineLaunchRequest.model_validate(record.pipeline_request),
    )

    return PipelineLaunchResult(
        request_id=updated_record.request_id,
        status=updated_record.status,
        operation=OperationType.apply,
        terraform_payload=record.terraform_payload,
        pipeline_request=record.pipeline_request,
        pipeline_id=record.gitlab_pipeline_id,
        pipeline_web_url=record.gitlab_pipeline_url,
    )


@app.post("/api/v1/ansible/runs", response_model=AnsibleRunResult)
def run_ansible_playbook(request: AnsibleRunRequest) -> AnsibleRunResult:
    vm_detail = get_vm_detail(request.target)
    vm_ansible = vm_detail.ansible if vm_detail is not None else {}

    project_path = request.project_path or vm_ansible.get("project_path") or settings.ansible_project_path
    ref = request.ref or vm_ansible.get("ref") or settings.ansible_ref
    limit = request.limit or vm_ansible.get("limit") or request.target
    if not project_path:
        raise HTTPException(status_code=400, detail="Ansible project path is not configured.")

    pipeline_request = build_ansible_only_launch_request(request)
    if vm_detail is not None:
        pipeline_request.variables["INVENTORY_SYNC_VM_JSON"] = build_inventory_sync_vm_payload(vm_detail.model_dump(mode="json"))

    try:
        pipeline_response = create_pipeline_for_project(project_path, pipeline_request)
    except GitLabClientError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc), "target": request.target}) from exc

    return AnsibleRunResult(
        requested_by=request.requested_by,
        target=request.target,
        playbook=request.playbook,
        project_path=project_path,
        ref=ref,
        limit=limit,
        service_profiles=request.service_profiles,
        pipeline_id=pipeline_response.get("id"),
        pipeline_web_url=pipeline_response.get("web_url"),
    )
