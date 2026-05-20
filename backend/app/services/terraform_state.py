from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings


class TerraformStateError(RuntimeError):
    pass


def list_live_vm_names() -> set[str] | None:
    diagnostics = get_live_vm_diagnostics()
    return diagnostics["vm_names"] if diagnostics["status"] == "ok" else None


def get_live_vm_diagnostics() -> dict[str, Any]:
    try:
        outputs = _load_state_outputs()
    except TerraformStateError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "vm_names": set(),
            "count": 0,
        }

    vm_ids = outputs.get("vm_ids", {}).get("value")
    if isinstance(vm_ids, dict):
        names = {
            str(name)
            for name, vm_id in vm_ids.items()
            if vm_id not in (None, "", "null")
        }
        if names:
            return {
                "status": "ok",
                "message": "Terraform state was read from S3 successfully.",
                "vm_names": names,
                "count": len(names),
            }

    vm_names = outputs.get("vm_names", {}).get("value")
    if isinstance(vm_names, list):
        names = {str(item) for item in vm_names}
        return {
            "status": "ok",
            "message": "Terraform state was read from S3 successfully.",
            "vm_names": names,
            "count": len(names),
        }

    return {
        "status": "error",
        "message": "Terraform state does not expose vm_ids or vm_names outputs.",
        "vm_names": set(),
        "count": 0,
    }


def _load_state_outputs() -> dict[str, Any]:
    state_document = _load_state_document()
    outputs = state_document.get("outputs")
    if not isinstance(outputs, dict):
        raise TerraformStateError("Terraform state does not contain an 'outputs' object.")
    return outputs


def _load_state_document() -> dict[str, Any]:
    config = _resolve_state_config()
    if not config["bucket"] or not config["key"]:
        raise TerraformStateError("Terraform state S3 bucket/key are not configured.")

    client_kwargs: dict[str, Any] = {}
    if config["region"]:
        client_kwargs["region_name"] = config["region"]
    if config["endpoint_url"]:
        client_kwargs["endpoint_url"] = config["endpoint_url"]
    if config["access_key_id"]:
        client_kwargs["aws_access_key_id"] = config["access_key_id"]
    if config["secret_access_key"]:
        client_kwargs["aws_secret_access_key"] = config["secret_access_key"]
    if config["session_token"]:
        client_kwargs["aws_session_token"] = config["session_token"]
    if config["force_path_style"]:
        client_kwargs["config"] = Config(s3={"addressing_style": "path"})

    try:
        client = boto3.client("s3", **client_kwargs)
        response = client.get_object(Bucket=config["bucket"], Key=config["key"])
        raw_state = response["Body"].read().decode("utf-8")
    except (BotoCoreError, ClientError, UnicodeDecodeError) as exc:
        raise TerraformStateError(f"Failed to read Terraform state from S3: {exc}") from exc

    try:
        parsed = json.loads(raw_state)
    except json.JSONDecodeError as exc:
        raise TerraformStateError(f"Terraform state is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise TerraformStateError("Terraform state JSON root is not an object.")

    return parsed


@lru_cache(maxsize=1)
def _resolve_state_config() -> dict[str, Any]:
    backend_config = _parse_backend_hcl(Path(settings.terraform_backend_config_file))

    endpoint_url = (
        settings.terraform_state_endpoint_url
        or backend_config.get("endpoint")
        or backend_config.get("endpoints.s3")
    )
    force_path_style = settings.terraform_state_force_path_style or _as_bool(
        backend_config.get("force_path_style") or backend_config.get("use_path_style")
    )

    return {
        "bucket": settings.terraform_state_bucket or backend_config.get("bucket"),
        "key": settings.terraform_state_key or backend_config.get("key"),
        "region": settings.terraform_state_region or backend_config.get("region"),
        "endpoint_url": endpoint_url,
        "access_key_id": settings.terraform_state_access_key_id or backend_config.get("access_key"),
        "secret_access_key": settings.terraform_state_secret_access_key or backend_config.get("secret_key"),
        "session_token": settings.terraform_state_session_token or backend_config.get("session_token"),
        "force_path_style": force_path_style,
    }


def _parse_backend_hcl(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    current_map_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if current_map_key and line == "}":
            current_map_key = None
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().rstrip(",")
        if value == "{":
            current_map_key = key
            continue
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if current_map_key:
            values[f"{current_map_key}.{key}"] = value
        else:
            values[key] = value
    return values


def _as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
