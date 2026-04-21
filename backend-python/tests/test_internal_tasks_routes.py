from app.api import internal_tasks


def test_internal_tasks_router_removes_dispatch_endpoint():
    paths = {route.path for route in internal_tasks.router.routes}

    assert "/tasks/dispatch" not in paths
    assert "/tasks/{task_id}/retry" in paths
    assert "/tasks/{task_id}/status" in paths
