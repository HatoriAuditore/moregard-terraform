import json

from app.models import ProvisionRequest, TerraformPayload, VmDefinition


def _vm_to_terraform_item(vm: VmDefinition) -> dict:
    return {
        "datacenter": vm.placement.datacenter,
        "cluster": vm.placement.cluster,
        "datastore": vm.placement.datastore,
        "vm_folder": vm.placement.vm_folder,
        "template": vm.template,
        "network": vm.network.network,
        "cpu": vm.hardware.cpu,
        "ram_mb": vm.hardware.ram_mb,
        "root_disk_gb": vm.hardware.root_disk_gb,
        "firmware": vm.hardware.firmware,
        "thin_provisioned": vm.hardware.thin_provisioned,
        "efi_secure_boot_enabled": vm.hardware.efi_secure_boot_enabled,
        "computer_name": vm.computer_name or vm.name,
        "domain": vm.network.domain,
        "dns_server_list": vm.network.dns_server_list,
        "dns_suffix_list": vm.network.dns_suffix_list,
        "ipv4_address": vm.network.ipv4_address,
        "ipv4_network": vm.network.ipv4_network,
        "ipv4_gateway": vm.network.ipv4_gateway,
    }


def build_terraform_payload(request: ProvisionRequest) -> TerraformPayload:
    payload = TerraformPayload(
        allow_unverified_ssl=request.defaults.allow_unverified_ssl,
        datacenter=request.defaults.datacenter,
        cluster=request.defaults.cluster,
        datastore=request.defaults.datastore,
        vm_folder=request.defaults.vm_folder,
        vms={vm.name: _vm_to_terraform_item(vm) for vm in request.vms},
    )
    return TerraformPayload.model_validate(_drop_none(payload.model_dump()))


def payload_to_tfvars_json(payload: TerraformPayload) -> str:
    return json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True)


def _drop_none(value):
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(v) for v in value]
    return value
