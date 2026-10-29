import pytest

from tasks import list_tasks


def test_filter_and_sort():
    assert [task["title"] for task in list_tasks("active")] == ["write"]
    assert [task["title"] for task in list_tasks("completed")] == ["read"]
    assert [task["title"] for task in list_tasks()] == ["read", "write"]


def test_reject_unknown():
    with pytest.raises(ValueError):
        list_tasks("unknown")
