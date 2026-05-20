from enum import Enum

from pydantic import BaseModel, Field, model_validator


class OperationType(str, Enum):
    plan = "plan"
    apply = "apply"


class RequestStatus(str, Enum):
    requested = "requested"
    planned = "planned"
    apply_pending = "apply_pending"
    applied = "applied"
    configure_pending = "configure_pending"
    configured = "configured"
    failed = "failed"


class VmNetworkConfig(BaseModel):
    network: str
    ipv4_address: str | None = None
    ipv4_network: int | None = None
    ipv4_gateway: str | None = None
    dns_server_list: list[str] = Field(default_factory=list)
    dns_suffix_list: list[str] = Field(default_factory=list)
    domain: str | None = None

    @model_validator(mode="after")
    def validate_static_network(self) -> "VmNetworkConfig":
        if (self.ipv4_address is None) != (self.ipv4_network is None):
            raise ValueError("Static IPv4 requires both ipv4_address and ipv4_network.")
        return self


class VmPlacement(BaseModel):
    datacenter: str | None = None
    cluster: str | None = None
    datastore: str | None = None
    vm_folder: str | None = None


class VmHardware(BaseModel):
    cpu: int | None = None
    ram_mb: int | None = None
    root_disk_gb: int | None = None
    firmware: str = "efi"
    thin_provisioned: bool = False
    efi_secure_boot_enabled: bool = False


class VmDefinition(BaseModel):
    name: str = Field(min_length=1)
    template: str = Field(min_length=1)
    computer_name: str | None = None
    placement: VmPlacement = Field(default_factory=VmPlacement)
    hardware: VmHardware = Field(default_factory=VmHardware)
    network: VmNetworkConfig


class ProvisioningDefaults(BaseModel):
    datacenter: str | None = None
    cluster: str | None = None
    datastore: str | None = None
    vm_folder: str | None = None
    allow_unverified_ssl: bool | None = None


class AnsibleConfig(BaseModel):
    enabled: bool = False
    project_path: str | None = None
    ref: str | None = None
    limit: str | None = None
    playbook: str | None = None
    service_profiles: list[str] = Field(default_factory=list)


class ProvisionRequest(BaseModel):
    request_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    operation: OperationType = OperationType.plan
    defaults: ProvisioningDefaults = Field(default_factory=ProvisioningDefaults)
    vms: list[VmDefinition] = Field(default_factory=list)
    ansible: AnsibleConfig = Field(default_factory=AnsibleConfig)
    allow_destroy_vm_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_vm_count(self) -> "ProvisionRequest":
        if not self.vms and not self.allow_destroy_vm_names:
            raise ValueError("Provision request must include at least one VM unless it is an explicit destroy request.")
        return self


class TerraformPayload(BaseModel):
    allow_unverified_ssl: bool | None = None
    datacenter: str | None = None
    cluster: str | None = None
    datastore: str | None = None
    vm_folder: str | None = None
    vms: dict[str, dict]


class PipelineVariables(BaseModel):
    variables: dict[str, str]


class PipelineLaunchRequest(BaseModel):
    ref: str = "main"
    variables: dict[str, str]


class PipelineLaunchResult(BaseModel):
    status: RequestStatus
    operation: OperationType
    terraform_payload: TerraformPayload
    pipeline_request: PipelineLaunchRequest
    request_id: str | None = None
    pipeline_id: int | None = None
    pipeline_web_url: str | None = None


class RequestRecord(BaseModel):
    request_id: str
    requested_by: str
    operation: OperationType
    status: RequestStatus
    gitlab_project_id: str
    gitlab_pipeline_id: int | None = None
    gitlab_pipeline_url: str | None = None
    request_payload: dict
    terraform_payload: dict
    pipeline_request: dict
    created_at: str
    updated_at: str


class ApplyRequest(BaseModel):
    requested_by: str = Field(min_length=1)


class AnsibleRunRequest(BaseModel):
    requested_by: str = Field(min_length=1)
    target: str = Field(min_length=1)
    playbook: str = Field(min_length=1)
    project_path: str | None = None
    ref: str | None = None
    limit: str | None = None
    service_profiles: list[str] = Field(default_factory=list)


class AnsibleRunResult(BaseModel):
    requested_by: str
    target: str
    playbook: str
    project_path: str
    ref: str
    limit: str
    service_profiles: list[str] = Field(default_factory=list)
    pipeline_id: int | None = None
    pipeline_web_url: str | None = None


class PipelineStatusResponse(BaseModel):
    request_id: str
    pipeline_id: int
    pipeline_status: str
    pipeline_web_url: str | None = None
    request_status: RequestStatus
    apply_job_status: str | None = None
    apply_available: bool = False
    plan_summary: dict[str, int] | None = None


class VmSummary(BaseModel):
    name: str
    request_id: str
    request_status: RequestStatus
    requested_by: str
    updated_at: str
    state_source: str = "request_history"
    live_present: bool | None = None
    template: str | None = None
    network: str | None = None
    ipv4_address: str | None = None
    domain: str | None = None
    cpu: int | None = None
    ram_mb: int | None = None
    root_disk_gb: int | None = None
    ansible_enabled: bool = False


class VmDetail(BaseModel):
    name: str
    request_id: str
    request_status: RequestStatus
    requested_by: str
    updated_at: str
    state_source: str = "request_history"
    live_present: bool | None = None
    vm: dict
    defaults: dict
    ansible: dict
