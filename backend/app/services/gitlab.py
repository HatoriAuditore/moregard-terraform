from __future__ import annotations

from urllib.parse import quote

import httpx

from app.config import settings
from app.models import PipelineLaunchRequest


class GitLabClientError(RuntimeError):
    pass


def create_pipeline(request: PipelineLaunchRequest) -> dict:
    return create_pipeline_for_project(settings.gitlab_project_id, request)


def create_pipeline_for_project(project_id: str, request: PipelineLaunchRequest) -> dict:
    if not settings.gitlab_token:
        raise GitLabClientError("VM_ORCH_GITLAB_TOKEN is not configured.")

    project_ref = quote(project_id, safe="")
    url = f"{settings.gitlab_base_url}/api/v4/projects/{project_ref}/pipeline"

    payload = {}
    if request.variables:
        payload["variables"] = [
            {"key": key, "value": value}
            for key, value in request.variables.items()
        ]

    request_kwargs = {
        "params": {"ref": request.ref},
        "headers": {
            "PRIVATE-TOKEN": settings.gitlab_token,
        },
    }

    if payload:
        request_kwargs["json"] = payload

    with httpx.Client(timeout=30.0, trust_env=True) as client:
        response = client.post(url, **request_kwargs)

    if response.status_code >= 400:
        raise GitLabClientError(
            f"GitLab pipeline creation failed with {response.status_code}: {response.text}"
        )

    return response.json()


def get_pipeline(pipeline_id: int) -> dict:
    if not settings.gitlab_token:
        raise GitLabClientError("VM_ORCH_GITLAB_TOKEN is not configured.")

    project_ref = quote(settings.gitlab_project_id, safe="")
    url = f"{settings.gitlab_base_url}/api/v4/projects/{project_ref}/pipelines/{pipeline_id}"

    try:
        with httpx.Client(timeout=settings.gitlab_timeout_seconds, trust_env=True) as client:
            response = client.get(
                url,
                headers={
                    "PRIVATE-TOKEN": settings.gitlab_token,
                },
            )
    except httpx.HTTPError as exc:
        raise GitLabClientError(f"GitLab request failed: {exc}") from exc

    if response.status_code >= 400:
        raise GitLabClientError(
            f"GitLab pipeline lookup failed with {response.status_code}: {response.text}"
        )

    return response.json()


def get_pipeline_jobs(pipeline_id: int) -> list[dict]:
    if not settings.gitlab_token:
        raise GitLabClientError("VM_ORCH_GITLAB_TOKEN is not configured.")

    project_ref = quote(settings.gitlab_project_id, safe="")
    url = f"{settings.gitlab_base_url}/api/v4/projects/{project_ref}/pipelines/{pipeline_id}/jobs"

    try:
        with httpx.Client(timeout=settings.gitlab_timeout_seconds, trust_env=True) as client:
            response = client.get(
                url,
                params={"include_retried": "true"},
                headers={
                    "PRIVATE-TOKEN": settings.gitlab_token,
                },
            )
    except httpx.HTTPError as exc:
        raise GitLabClientError(f"GitLab request failed: {exc}") from exc

    if response.status_code >= 400:
        raise GitLabClientError(
            f"GitLab pipeline jobs lookup failed with {response.status_code}: {response.text}"
        )

    return response.json()


def play_job(job_id: int) -> dict:
    if not settings.gitlab_token:
        raise GitLabClientError("VM_ORCH_GITLAB_TOKEN is not configured.")

    project_ref = quote(settings.gitlab_project_id, safe="")
    url = f"{settings.gitlab_base_url}/api/v4/projects/{project_ref}/jobs/{job_id}/play"

    try:
        with httpx.Client(timeout=settings.gitlab_timeout_seconds, trust_env=True) as client:
            response = client.post(
                url,
                headers={
                    "PRIVATE-TOKEN": settings.gitlab_token,
                },
            )
    except httpx.HTTPError as exc:
        raise GitLabClientError(f"GitLab request failed: {exc}") from exc

    if response.status_code >= 400:
        raise GitLabClientError(
            f"GitLab job play failed with {response.status_code}: {response.text}"
        )

    return response.json()


def get_job_artifact_text(job_id: int, artifact_path: str) -> str:
    if not settings.gitlab_token:
        raise GitLabClientError("VM_ORCH_GITLAB_TOKEN is not configured.")

    project_ref = quote(settings.gitlab_project_id, safe="")
    artifact_ref = quote(artifact_path, safe="/")
    url = f"{settings.gitlab_base_url}/api/v4/projects/{project_ref}/jobs/{job_id}/artifacts/{artifact_ref}"

    try:
        with httpx.Client(timeout=settings.gitlab_timeout_seconds, trust_env=True) as client:
            response = client.get(
                url,
                headers={
                    "PRIVATE-TOKEN": settings.gitlab_token,
                },
            )
    except httpx.HTTPError as exc:
        raise GitLabClientError(f"GitLab request failed: {exc}") from exc

    if response.status_code >= 400:
        raise GitLabClientError(
            f"GitLab artifact download failed with {response.status_code}: {response.text}"
        )

    return response.text


def get_project(project_id: str) -> dict:
    if not settings.gitlab_token:
        raise GitLabClientError("VM_ORCH_GITLAB_TOKEN is not configured.")

    project_ref = quote(project_id, safe="")
    url = f"{settings.gitlab_base_url}/api/v4/projects/{project_ref}"

    try:
        with httpx.Client(timeout=settings.gitlab_timeout_seconds, trust_env=True) as client:
            response = client.get(
                url,
                headers={
                    "PRIVATE-TOKEN": settings.gitlab_token,
                },
            )
    except httpx.HTTPError as exc:
        raise GitLabClientError(f"GitLab request failed: {exc}") from exc

    if response.status_code >= 400:
        raise GitLabClientError(
            f"GitLab project lookup failed with {response.status_code}: {response.text}"
        )

    return response.json()
