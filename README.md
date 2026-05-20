# Terraform Backend

This repository contains the infrastructure layer for provisioning virtual machines in vSphere and the backend API that prepares and launches GitLab pipelines for those changes.

## Repository structure

- `.gitlab-ci.yml`  
  Terraform pipeline definition with `validate`, `plan`, `apply`, and optional downstream Ansible trigger.
- `main.tf`, `variables.tf`, `providers.tf`, `outputs.tf`  
  Root Terraform configuration.
- `modules/vm_from_template/`  
  Reusable module for cloning and customizing VMs from a template.
- `backend/`  
  FastAPI service that validates requests, stores request history, generates Terraform payloads, and starts GitLab pipelines.

## What this repository does

The Terraform layer manages a map of virtual machines. Each VM can define:

- template name
- network / VLAN
- CPU and RAM
- root disk size
- Linux guest customization
- DNS settings
- static IPv4 settings

The backend service converts higher-level provisioning requests into a Terraform-compatible payload and launches the GitLab pipeline that applies the change.

Ansible configuration is intentionally kept in a separate repository. This repository only coordinates the downstream trigger through GitLab pipeline variables.

## Terraform workflow

The GitLab pipeline in this repository uses the following stages:

1. `validate`  
   Checks formatting and Terraform validation.
2. `plan`  
   Builds the Terraform execution plan and exports a JSON representation.
3. `apply`  
   Applies the exact generated plan artifact.
4. `configure_vm`  
   Optionally triggers a downstream Ansible project after apply.

The downstream Ansible stage runs only when:

- `CONFIGURE_WITH_ANSIBLE=true`
- `ANSIBLE_PROJECT_PATH` is set
- `ANSIBLE_REF` is set

## Backend API

The backend service lives in `backend/` and is implemented with FastAPI.

Main responsibilities:

- accept VM provisioning requests
- generate Terraform payloads
- persist request history in SQLite
- trigger GitLab pipelines
- expose request and pipeline status to the CLI
- trigger the saved-request apply flow through the backend API
- support direct Ansible-only runs

Main API endpoints:

- `POST /api/v1/provisioning/payload`
- `POST /api/v1/provisioning/requests`
- `GET /api/v1/provisioning/requests`
- `GET /api/v1/provisioning/requests/{request_id}`
- `GET /api/v1/vms`
- `GET /api/v1/vms/{name}`
- `GET /api/v1/provisioning/requests/{request_id}/pipeline`
- `POST /api/v1/provisioning/requests/{request_id}/apply`
- `POST /api/v1/ansible/runs`

## Input model

A provisioning request contains:

- request metadata
- shared defaults for placement
- one or more VM definitions
- optional Ansible follow-up settings

Each VM can override shared defaults when needed.

## Source of truth

The backend uses two data sources:

- SQLite request history for request tracking and operator actions
- Terraform state, when available, as a best-effort source for currently existing VM names

If Terraform state cannot be read, the backend falls back to request history without failing the API.

## Safe usage notes

This repository is declarative: the `vms` map represents the full desired state.

That means a request which omits already managed machines may produce a plan that removes them. Any operator-facing tooling should therefore build requests carefully and include all required VMs for the target environment.

## Configuration

Typical backend environment variables:

- `VM_ORCH_GITLAB_BASE_URL`
- `VM_ORCH_GITLAB_PROJECT_ID`
- `VM_ORCH_GITLAB_TOKEN`
- `VM_ORCH_GITLAB_REF`
- `VM_ORCH_TERRAFORM_BACKEND_CONFIG_FILE`
- `VM_ORCH_TERRAFORM_VARS_FILE`
- `VM_ORCH_ANSIBLE_PROJECT_PATH`
- `VM_ORCH_ANSIBLE_REF`
- `VM_ORCH_SQLITE_DB_PATH`

Do not commit real tokens, real backend config paths, or environment-specific secrets to the repository.

The backend expects its real Terraform backend config at:

```text
backend/config/backend.hcl
```

The repository tracks only:

```text
backend/config/backend.hcl.example
```

On a server, copy the example to `backend/config/backend.hcl` and fill in the real environment values there.

## Example files

The repository includes sanitized example request files in `backend/examples/`.

They are intended to show request structure only. Replace placeholder values with environment-specific settings before use.
