from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "VM Orchestrator API"
    env: str = "dev"
    gitlab_base_url: str = "https://gitlab.example.com"
    gitlab_project_id: str = "group/terraform-backend"
    gitlab_token: str | None = None
    gitlab_ref: str = "main"
    gitlab_timeout_seconds: float = 30.0
    terraform_binary: str = "terraform"
    terraform_vars_file: str = "generated.auto.tfvars.json"
    terraform_backend_config_file: str = str(BACKEND_DIR / "config" / "backend.hcl")
    terraform_pipeline_backend_config_file: str = "/opt/tf-vsphere/backend.hcl"
    terraform_working_directory: str = str(BACKEND_DIR.parent)
    terraform_state_bucket: str | None = None
    terraform_state_key: str | None = None
    terraform_state_region: str | None = None
    terraform_state_endpoint_url: str | None = None
    terraform_state_access_key_id: str | None = None
    terraform_state_secret_access_key: str | None = None
    terraform_state_session_token: str | None = None
    terraform_state_force_path_style: bool = False
    ansible_project_path: str | None = None
    ansible_ref: str = "main"
    sqlite_db_path: str = "data/vm_orchestrator.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VM_ORCH_",
        extra="ignore",
    )


settings = Settings()
