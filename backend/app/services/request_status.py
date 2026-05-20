from app.models import OperationType, RequestStatus


def map_pipeline_status_to_request_status(
    *,
    operation: OperationType,
    pipeline_status: str,
    ansible_enabled: bool = False,
) -> RequestStatus:
    normalized = pipeline_status.lower()

    if normalized in {"failed", "canceled", "canceling", "skipped"}:
        return RequestStatus.failed

    if operation == OperationType.plan:
        if normalized in {"created", "pending", "preparing", "waiting_for_resource", "running", "manual"}:
            return RequestStatus.planned
        if normalized == "success":
            return RequestStatus.apply_pending
        return RequestStatus.planned

    if normalized in {"created", "pending", "preparing", "waiting_for_resource", "running", "manual"}:
        return RequestStatus.apply_pending
    if normalized == "success":
        return RequestStatus.configure_pending if ansible_enabled else RequestStatus.applied

    return RequestStatus.apply_pending
