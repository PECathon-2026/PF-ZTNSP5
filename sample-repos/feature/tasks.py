TASKS = [{"title": "write", "status": "active"}, {"title": "read", "status": "completed"}]


def list_tasks(status=None):
    return sorted(TASKS, key=lambda task: task["title"])
