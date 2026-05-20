import base64
import json

from app.config import settings
from app.models import AnsibleRunRequest, PipelineLaunchRequest, PipelineVariables, ProvisionRequest
from app.services.terraform_payload import build_terraform_payload, payload_to_tfvars_json


def build_pipeline_variables(request: ProvisionRequest) -> PipelineVariables:
    payload = build_terraform_payload(request)
    tfvars_json = payload_to_tfvars_json(payload)

    ansible_project_path = request.ansible.project_path or settings.ansible_project_path
    ansible_ref = request.ansible.ref or settings.ansible_ref
    vm_names = [vm.name for vm in request.vms]

    variables = {
        "TF_BACKEND_CONFIG_FILE": settings.terraform_pipeline_backend_config_file,
        "TF_VARS_FILE": settings.terraform_vars_file,
        "VM_REQUEST_ID": request.request_id,
        "VM_REQUESTED_BY": request.requested_by,
        "VM_OPERATION": request.operation.value,
        "VM_NAMES": ",".join(vm_names),
        "VM_NAMES_JSON": json.dumps(vm_names),
        "TF_VARS_CONTENT_B64": base64.b64encode(tfvars_json.encode("utf-8")).decode("ascii"),
        "CONFIGURE_WITH_ANSIBLE": str(request.ansible.enabled).lower(),
        "ALLOW_DESTROY_VM_NAMES_JSON": json.dumps(request.allow_destroy_vm_names),
    }

    if request.allow_destroy_vm_names:
        variables["ALLOW_DESTROY_VM_NAMES"] = ",".join(request.allow_destroy_vm_names)

    if request.ansible.enabled and ansible_project_path:
        variables["ANSIBLE_PROJECT_PATH"] = ansible_project_path
    if request.ansible.enabled and ansible_ref:
        variables["ANSIBLE_REF"] = ansible_ref
    if request.ansible.limit:
        variables["ANSIBLE_LIMIT"] = request.ansible.limit
    if request.ansible.playbook:
        variables["ANSIBLE_PLAYBOOK"] = request.ansible.playbook
    ansible_extra_vars = _build_ansible_extra_vars(request.ansible.service_profiles)
    if ansible_extra_vars:
        variables["ANSIBLE_EXTRA_VARS_JSON"] = json.dumps(ansible_extra_vars)

    return PipelineVariables(variables=variables)


def build_pipeline_launch_request(request: ProvisionRequest) -> PipelineLaunchRequest:
    pipeline_variables = build_pipeline_variables(request)
    return PipelineLaunchRequest(ref=settings.gitlab_ref, variables=pipeline_variables.variables)


def build_ansible_only_launch_request(request: AnsibleRunRequest) -> PipelineLaunchRequest:
    ansible_project_path = request.project_path or settings.ansible_project_path
    ansible_ref = request.ref or settings.ansible_ref
    ansible_limit = request.limit or request.target
    extra_vars = _build_ansible_extra_vars(request.service_profiles)

    variables = {
        "VM_REQUEST_ID": f"ANSIBLE-{request.target}",
        "VM_REQUESTED_BY": request.requested_by,
        "VM_OPERATION": "ansible_run",
        "VM_NAMES": request.target,
        "VM_NAMES_JSON": json.dumps([request.target]),
        "ANSIBLE_LIMIT": ansible_limit,
        "ANSIBLE_PLAYBOOK": request.playbook,
    }
    if extra_vars:
        variables["ANSIBLE_EXTRA_VARS_JSON"] = json.dumps(extra_vars)

    return PipelineLaunchRequest(ref=ansible_ref, variables=variables)


def _build_ansible_extra_vars(service_profiles: list[str]) -> dict[str, object]:
    extra_vars: dict[str, object] = {}
    if service_profiles:
        extra_vars["vm_service_profiles"] = service_profiles
    return extra_vars


def build_inventory_sync_vm_payload(vm_detail: dict) -> str:
    vm = vm_detail.get("vm", {})
    network = vm.get("network", {})
    payload = {
        "name": vm_detail.get("name"),
        "computer_name": vm.get("computer_name") or vm_detail.get("name"),
        "ipv4_address": network.get("ipv4_address"),
        "domain": network.get("domain"),
        "dns_suffix_list": network.get("dns_suffix_list") or [],
    }
    return json.dumps(payload)
