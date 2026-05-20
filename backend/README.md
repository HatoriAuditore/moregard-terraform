# Backend API

This directory contains the FastAPI service used as the orchestration backend for VM requests.

## Purpose

The service acts as a control layer between an operator-facing client and the Terraform / Ansible GitLab pipelines.

It is responsible for:

- validating incoming provisioning requests
- transforming requests into Terraform payloads
- launching GitLab pipelines
- storing request history
- exposing pipeline and VM status over HTTP
- launching Ansible-only runs when infrastructure changes are not required

## Main components

- `app/main.py`  
  FastAPI routes and request handlers.
- `app/models.py`  
  Pydantic models for requests and responses.
- `app/services/terraform_payload.py`  
  Conversion from API request model to Terraform payload.
- `app/services/pipeline.py`  
  GitLab variable generation for Terraform and Ansible runs.
- `app/services/gitlab.py`  
  GitLab API client for pipeline creation and status lookup.
- `app/services/terraform_state.py`  
  Best-effort lookup of live VM names from Terraform state.
- `app/repositories/request_repository.py`  
  Persistence and VM summary/detail reconstruction from stored requests.
- `app/database.py`  
  SQLite initialization and connection handling.

## Runtime behavior

1. The client sends a provisioning or Ansible request.
2. The backend validates and normalizes the request.
3. A Terraform-compatible payload and GitLab pipeline variables are generated.
4. The backend creates a GitLab pipeline.
5. Request metadata is stored in SQLite.
6. The client can poll request or pipeline status through the API.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Required environment variables

Expected values come from a local `.env` file or environment:

- `VM_ORCH_GITLAB_BASE_URL`
- `VM_ORCH_GITLAB_PROJECT_ID`
- `VM_ORCH_GITLAB_TOKEN`
- `VM_ORCH_GITLAB_REF`
- `VM_ORCH_TERRAFORM_BACKEND_CONFIG_FILE`
- `VM_ORCH_TERRAFORM_VARS_FILE`
- `VM_ORCH_ANSIBLE_PROJECT_PATH`
- `VM_ORCH_ANSIBLE_REF`
- `VM_ORCH_SQLITE_DB_PATH`

Keep all secrets and environment-specific values outside source control.

## Terraform state backend config

The backend expects a local Terraform backend config file at:

```text
backend/config/backend.hcl
```

The repository includes a tracked example:

```text
backend/config/backend.hcl.example
```

Typical setup on the server:

```bash
cp backend/config/backend.hcl.example backend/config/backend.hcl
```

Then replace placeholder values with the real S3 backend settings for the environment.

The real `backend.hcl` file is intentionally ignored by Git.
