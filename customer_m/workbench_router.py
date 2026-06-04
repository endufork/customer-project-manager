from .database import db_connect
from .modules.workbench import (
    apply_template,
    create_issue,
    create_task,
    delete_issue,
    delete_task,
    get_workbench_project,
    list_workbench_inbox,
    list_workbench_projects,
    list_workbench_tasks,
    review_deliverable,
    submit_task_file,
    update_issue,
    update_task,
)


class WorkbenchRouterMixin:
    def handle_workbench_get(self, path: str, query: dict[str, list[str]]) -> bool:
        if path == "/api/workbench/projects":
            return self.api_workbench_projects(query)
        if path == "/api/workbench/inbox":
            return self.api_workbench_inbox(query)
        if path == "/api/workbench/tasks":
            return self.api_workbench_tasks(query)
        if path.startswith("/api/workbench/projects/"):
            project_id = path.rsplit("/", 1)[1]
            return self.api_workbench_project(project_id)
        return False

    def api_workbench_projects(self, query: dict[str, list[str]]) -> bool:
        with db_connect() as conn:
            payload = list_workbench_projects(conn, query)
        self.send_json(payload)
        return True

    def api_workbench_inbox(self, query: dict[str, list[str]]) -> bool:
        with db_connect() as conn:
            payload = list_workbench_inbox(conn, query)
        self.send_json(payload)
        return True

    def api_workbench_tasks(self, query: dict[str, list[str]]) -> bool:
        with db_connect() as conn:
            payload = list_workbench_tasks(conn, query)
        self.send_json(payload)
        return True

    def api_workbench_project(self, project_id: str) -> bool:
        with db_connect() as conn:
            payload = get_workbench_project(conn, project_id)
        self.send_json(payload)
        return True

    def handle_workbench_post(self, path: str) -> bool:
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[2] == "projects" and parts[4] == "tasks":
            self.require_role("pm")
            data = self.read_json()
            with db_connect() as conn:
                payload = create_task(conn, parts[3], data)
                conn.commit()
            self.send_json(payload, 201)
            return True
        if len(parts) == 5 and parts[2] == "projects" and parts[4] == "issues":
            self.require_role("engineer", "pm")
            data = self.read_json()
            with db_connect() as conn:
                payload = create_issue(conn, parts[3], data)
                conn.commit()
            self.send_json(payload, 201)
            return True
        if len(parts) == 5 and parts[2] == "projects" and parts[4] == "templates":
            self.require_role("pm")
            data = self.read_json()
            with db_connect() as conn:
                payload = apply_template(conn, parts[3], data.get("template"))
                conn.commit()
            self.send_json(payload)
            return True
        if len(parts) == 5 and parts[2] == "tasks" and parts[4] == "deliverables":
            self.require_role("engineer", "pm")
            fields, filename, content = self.read_multipart()
            with db_connect() as conn:
                payload = submit_task_file(conn, parts[3], filename, content, fields)
                conn.commit()
            self.send_json(payload, 201)
            return True
        return False

    def handle_workbench_patch(self, path: str) -> bool:
        parts = path.strip("/").split("/")
        data = self.read_json()
        if len(parts) == 4 and parts[2] == "tasks":
            self.require_role("engineer", "pm")
            with db_connect() as conn:
                payload = update_task(conn, parts[3], data)
                conn.commit()
            self.send_json(payload)
            return True
        if len(parts) == 4 and parts[2] == "issues":
            self.require_role("pm")
            with db_connect() as conn:
                payload = update_issue(conn, parts[3], data)
                conn.commit()
            self.send_json(payload)
            return True
        if len(parts) == 4 and parts[2] == "deliverables":
            self.require_role("pm")
            with db_connect() as conn:
                payload = review_deliverable(conn, parts[3], data)
                conn.commit()
            self.send_json(payload)
            return True
        return False

    def handle_workbench_delete(self, path: str) -> bool:
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[2] == "tasks":
            self.require_role("pm")
            with db_connect() as conn:
                payload = delete_task(conn, parts[3])
                conn.commit()
            self.send_json(payload)
            return True
        if len(parts) == 4 and parts[2] == "issues":
            self.require_role("pm")
            with db_connect() as conn:
                payload = delete_issue(conn, parts[3])
                conn.commit()
            self.send_json(payload)
            return True
        return False
