from work_frontier.interfaces.api.services import InMemoryControlPlane
from work_frontier.interfaces.processes.scheduler import run_scheduler_once
from work_frontier.interfaces.processes.worker import run_worker_once


def test_web_worker_scheduler_share_one_application_contract() -> None:
    service = InMemoryControlPlane.seeded()
    context = service.validate_session(
        token=next(iter(service.sessions)),
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        actor_hint=None,
    )
    job = service.schedule_sync(context)
    assert job.state == "persisted"
    assert run_scheduler_once(service) == "scheduled:1"
    assert run_worker_once(service) == f"completed:{job.job_id}"
    assert run_worker_once(service) == "idle"
