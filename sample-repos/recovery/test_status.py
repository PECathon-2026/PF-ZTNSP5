from status import task_status


def test_completed_task():
    assert task_status(True) == "completed"


def test_active_task():
    assert task_status(False) == "active"
