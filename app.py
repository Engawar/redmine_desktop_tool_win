import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Redmine Ticket Export/Import Tool"
CONFIG_FILENAME = "config.json"
DEFAULT_EXPORT_DIR = "exports"


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
CONFIG_PATH = BASE_DIR / CONFIG_FILENAME
EXPORT_DIR = BASE_DIR / DEFAULT_EXPORT_DIR


DEFAULT_CONFIG = {
    "redmine_url": "https://your-redmine.example.com",
    "api_key": "PUT_YOUR_API_KEY_HERE",
    "default_project_identifier": "",
    "default_export_dir": "exports",
    "verify_ssl": True,
    "timeout_seconds": 30,
    "page_size": 100,
}


class RedmineError(Exception):
    pass


@dataclass
class AppConfig:
    redmine_url: str
    api_key: str
    default_project_identifier: str
    default_export_dir: str
    verify_ssl: bool
    timeout_seconds: int
    page_size: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        merged = {**DEFAULT_CONFIG, **(data or {})}
        return cls(
            redmine_url=str(merged["redmine_url"]).rstrip("/"),
            api_key=str(merged["api_key"]),
            default_project_identifier=str(merged["default_project_identifier"]),
            default_export_dir=str(merged["default_export_dir"]),
            verify_ssl=bool(merged["verify_ssl"]),
            timeout_seconds=int(merged["timeout_seconds"]),
            page_size=int(merged["page_size"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "redmine_url": self.redmine_url,
            "api_key": self.api_key,
            "default_project_identifier": self.default_project_identifier,
            "default_export_dir": self.default_export_dir,
            "verify_ssl": self.verify_ssl,
            "timeout_seconds": self.timeout_seconds,
            "page_size": self.page_size,
        }


def ensure_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return AppConfig.from_dict(data)


def save_config(config: AppConfig) -> None:
    CONFIG_PATH.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class RedmineClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "X-Redmine-API-Key": config.api_key,
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.config.redmine_url}{path}"
        kwargs.setdefault("timeout", self.config.timeout_seconds)
        kwargs.setdefault("verify", self.config.verify_ssl)
        response = self.session.request(method, url, **kwargs)
        if response.status_code >= 400:
            text = response.text[:500]
            raise RedmineError(f"{response.status_code} {response.reason}: {text}")
        return response

    def test_connection(self) -> Dict[str, Any]:
        return self._request("GET", "/users/current.json").json()["user"]

    def get_projects(self) -> List[Dict[str, Any]]:
        offset = 0
        limit = 100
        projects: List[Dict[str, Any]] = []
        while True:
            resp = self._request("GET", f"/projects.json?limit={limit}&offset={offset}")
            data = resp.json()
            chunk = data.get("projects", [])
            projects.extend(chunk)
            total = data.get("total_count", len(projects))
            offset += limit
            if offset >= total:
                break
        return sorted(projects, key=lambda x: x.get("identifier", ""))

    def get_issues(self, project_identifier: str) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        offset = 0
        limit = self.config.page_size
        while True:
            path = (
                "/issues.json"
                f"?project_id={project_identifier}"
                f"&status_id=*"
                f"&include=journals"
                f"&limit={limit}"
                f"&offset={offset}"
            )
            data = self._request("GET", path).json()
            chunk = data.get("issues", [])
            issues.extend(chunk)
            total = data.get("total_count", len(issues))
            offset += limit
            if offset >= total:
                break
        return issues

    def update_issue(self, issue_id: int, payload: Dict[str, Any]) -> None:
        body = {"issue": payload}
        self._request("PUT", f"/issues/{issue_id}.json", data=json.dumps(body, ensure_ascii=False))


def normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    assigned = issue.get("assigned_to") or {}
    priority = issue.get("priority") or {}
    status = issue.get("status") or {}
    tracker = issue.get("tracker") or {}
    author = issue.get("author") or {}
    project = issue.get("project") or {}
    return {
        "id": issue.get("id", ""),
        "project_id": project.get("id", ""),
        "project_name": project.get("name", ""),
        "tracker_id": tracker.get("id", ""),
        "tracker_name": tracker.get("name", ""),
        "subject": issue.get("subject", ""),
        "description": issue.get("description", ""),
        "status_id": status.get("id", ""),
        "status_name": status.get("name", ""),
        "priority_id": priority.get("id", ""),
        "priority_name": priority.get("name", ""),
        "author_id": author.get("id", ""),
        "author_name": author.get("name", ""),
        "assigned_to_id": assigned.get("id", ""),
        "assigned_to_name": assigned.get("name", ""),
        "start_date": issue.get("start_date", ""),
        "due_date": issue.get("due_date", ""),
        "done_ratio": issue.get("done_ratio", ""),
        "estimated_hours": issue.get("estimated_hours", ""),
        "spent_hours": issue.get("spent_hours", ""),
        "created_on": issue.get("created_on", ""),
        "updated_on": issue.get("updated_on", ""),
        "lock_version": issue.get("lock_version", ""),
        "notes_append": "",
        "description_append": "",
    }


EXPORT_HEADERS = [
    "id",
    "project_id",
    "project_name",
    "tracker_id",
    "tracker_name",
    "subject",
    "description",
    "status_id",
    "status_name",
    "priority_id",
    "priority_name",
    "author_id",
    "author_name",
    "assigned_to_id",
    "assigned_to_name",
    "start_date",
    "due_date",
    "done_ratio",
    "estimated_hours",
    "spent_hours",
    "created_on",
    "updated_on",
    "lock_version",
    "notes_append",
    "description_append",
]


UPDATE_FIELD_CASTS = {
    "status_id": int,
    "assigned_to_id": int,
    "priority_id": int,
    "done_ratio": int,
    "estimated_hours": float,
}

ALLOWED_UPDATE_FIELDS = {
    "subject",
    "status_id",
    "assigned_to_id",
    "priority_id",
    "due_date",
    "start_date",
    "done_ratio",
    "estimated_hours",
}


class MainWindow(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=12)
        self.root = root
        self.config_data = ensure_config()
        self.client: Optional[RedmineClient] = None
        self.projects_map: Dict[str, str] = {}
        self.pack(fill=tk.BOTH, expand=True)
        self._build_ui()
        self._load_config_to_ui()

    def _build_ui(self) -> None:
        self.root.title(APP_NAME)
        self.root.geometry("860x640")

        top = ttk.LabelFrame(self, text="接続設定", padding=10)
        top.pack(fill=tk.X)

        self.url_var = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.verify_ssl_var = tk.BooleanVar(value=True)
        self.timeout_var = tk.StringVar(value="30")
        self.page_size_var = tk.StringVar(value="100")

        ttk.Label(top, text="Redmine URL").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(top, textvariable=self.url_var, width=70).grid(row=0, column=1, sticky=tk.EW, padx=6)

        ttk.Label(top, text="API Key").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(top, textvariable=self.api_key_var, show="*", width=70).grid(row=1, column=1, sticky=tk.EW, padx=6)

        opt = ttk.Frame(top)
        opt.grid(row=2, column=1, sticky=tk.W, pady=4)
        ttk.Checkbutton(opt, text="SSL証明書を検証する", variable=self.verify_ssl_var).pack(side=tk.LEFT)
        ttk.Label(opt, text="Timeout(s)").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Entry(opt, textvariable=self.timeout_var, width=8).pack(side=tk.LEFT)
        ttk.Label(opt, text="Page size").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Entry(opt, textvariable=self.page_size_var, width=8).pack(side=tk.LEFT)

        btns = ttk.Frame(top)
        btns.grid(row=3, column=1, sticky=tk.W, pady=(8, 0))
        ttk.Button(btns, text="設定保存", command=self.save_settings_clicked).pack(side=tk.LEFT)
        ttk.Button(btns, text="接続確認", command=self.test_connection_clicked).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="PJ一覧取得", command=self.load_projects_clicked).pack(side=tk.LEFT)
        top.columnconfigure(1, weight=1)

        middle = ttk.LabelFrame(self, text="エクスポート / インポート", padding=10)
        middle.pack(fill=tk.X, pady=10)

        self.project_var = tk.StringVar()
        ttk.Label(middle, text="対象プロジェクト").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.project_combo = ttk.Combobox(middle, textvariable=self.project_var, width=60, state="readonly")
        self.project_combo.grid(row=0, column=1, sticky=tk.EW, padx=6)

        self.export_path_var = tk.StringVar(value=str(EXPORT_DIR))
        ttk.Label(middle, text="出力先フォルダ").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(middle, textvariable=self.export_path_var, width=60).grid(row=1, column=1, sticky=tk.EW, padx=6)
        ttk.Button(middle, text="参照", command=self.choose_export_dir).grid(row=1, column=2, sticky=tk.W)

        acts = ttk.Frame(middle)
        acts.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))
        ttk.Button(acts, text="CSVエクスポート", command=self.export_clicked).pack(side=tk.LEFT)
        ttk.Button(acts, text="CSVインポート", command=self.import_clicked).pack(side=tk.LEFT, padx=6)
        ttk.Button(acts, text="CSV雛形を保存", command=self.template_clicked).pack(side=tk.LEFT)
        middle.columnconfigure(1, weight=1)

        logframe = ttk.LabelFrame(self, text="ログ", padding=10)
        logframe.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(logframe, wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log("アプリを起動しました。設定保存後、接続確認→PJ一覧取得の順でご利用ください。")

    def _load_config_to_ui(self) -> None:
        c = self.config_data
        self.url_var.set(c.redmine_url)
        self.api_key_var.set(c.api_key)
        self.verify_ssl_var.set(c.verify_ssl)
        self.timeout_var.set(str(c.timeout_seconds))
        self.page_size_var.set(str(c.page_size))
        export_dir = BASE_DIR / c.default_export_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        self.export_path_var.set(str(export_dir))

    def build_config_from_ui(self) -> AppConfig:
        return AppConfig(
            redmine_url=self.url_var.get().strip().rstrip("/"),
            api_key=self.api_key_var.get().strip(),
            default_project_identifier=self.config_data.default_project_identifier,
            default_export_dir=Path(self.export_path_var.get().strip() or DEFAULT_EXPORT_DIR).name,
            verify_ssl=self.verify_ssl_var.get(),
            timeout_seconds=int(self.timeout_var.get().strip() or 30),
            page_size=int(self.page_size_var.get().strip() or 100),
        )

    def save_settings_clicked(self) -> None:
        try:
            config = self.build_config_from_ui()
            save_config(config)
            self.config_data = config
            self.client = RedmineClient(config)
            self.log("設定を保存しました。")
            messagebox.showinfo(APP_NAME, "設定を保存しました。")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"設定保存に失敗しました。\n{e}")

    def ensure_client(self) -> RedmineClient:
        if self.client is None:
            self.config_data = self.build_config_from_ui()
            self.client = RedmineClient(self.config_data)
        return self.client

    def test_connection_clicked(self) -> None:
        try:
            client = self.ensure_client()
            user = client.test_connection()
            self.log(f"接続成功: {user.get('firstname', '')} {user.get('lastname', '')} / login={user.get('login', '')}")
            messagebox.showinfo(APP_NAME, f"接続成功\nUser: {user.get('login', '')}")
        except Exception as e:
            self.log(f"接続失敗: {e}")
            messagebox.showerror(APP_NAME, f"接続に失敗しました。\n{e}")

    def load_projects_clicked(self) -> None:
        try:
            client = self.ensure_client()
            projects = client.get_projects()
            self.projects_map = {p["identifier"]: p["name"] for p in projects}
            values = [f"{k} | {v}" for k, v in self.projects_map.items()]
            self.project_combo["values"] = values
            default = self.config_data.default_project_identifier
            if default and default in self.projects_map:
                self.project_var.set(f"{default} | {self.projects_map[default]}")
            elif values:
                self.project_var.set(values[0])
            self.log(f"PJ一覧取得完了: {len(projects)}件")
        except Exception as e:
            self.log(f"PJ一覧取得失敗: {e}")
            messagebox.showerror(APP_NAME, f"PJ一覧取得に失敗しました。\n{e}")

    def choose_export_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.export_path_var.get() or str(BASE_DIR))
        if path:
            self.export_path_var.set(path)

    def current_project_identifier(self) -> str:
        raw = self.project_var.get().strip()
        if not raw:
            return ""
        return raw.split("|", 1)[0].strip()

    def export_clicked(self) -> None:
        project_identifier = self.current_project_identifier()
        if not project_identifier:
            messagebox.showwarning(APP_NAME, "対象プロジェクトを選択してください。")
            return
        try:
            client = self.ensure_client()
            issues = client.get_issues(project_identifier)
            rows = [normalize_issue(i) for i in issues]
            export_dir = Path(self.export_path_var.get().strip() or EXPORT_DIR)
            export_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = export_dir / f"issues_{project_identifier}_{ts}.csv"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=EXPORT_HEADERS)
                writer.writeheader()
                writer.writerows(rows)
            self.log(f"CSVエクスポート完了: {csv_path} ({len(rows)}件)")
            messagebox.showinfo(APP_NAME, f"CSVを出力しました。\n{csv_path}")
        except Exception as e:
            self.log(f"CSVエクスポート失敗: {e}")
            messagebox.showerror(APP_NAME, f"CSVエクスポートに失敗しました。\n{e}")

    def template_clicked(self) -> None:
        try:
            export_dir = Path(self.export_path_var.get().strip() or EXPORT_DIR)
            export_dir.mkdir(parents=True, exist_ok=True)
            path = export_dir / "issues_update_template.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=EXPORT_HEADERS)
                writer.writeheader()
                writer.writerow({
                    "id": "123",
                    "subject": "件名を変える場合のみ記入",
                    "status_id": "1",
                    "assigned_to_id": "5",
                    "priority_id": "2",
                    "due_date": "2026-03-31",
                    "notes_append": "追記コメント",
                    "description_append": "説明追記",
                })
            self.log(f"CSV雛形を保存しました: {path}")
            messagebox.showinfo(APP_NAME, f"CSV雛形を保存しました。\n{path}")
        except Exception as e:
            self.log(f"CSV雛形保存失敗: {e}")
            messagebox.showerror(APP_NAME, f"CSV雛形保存に失敗しました。\n{e}")

    def import_clicked(self) -> None:
        path = filedialog.askopenfilename(
            title="更新用CSVを選択",
            filetypes=[("CSV", "*.csv")],
            initialdir=self.export_path_var.get() or str(BASE_DIR),
        )
        if not path:
            return
        try:
            client = self.ensure_client()
            ok_count = 0
            ng_count = 0
            errors: List[Dict[str, Any]] = []
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    issue_id = (row.get("id") or "").strip()
                    if not issue_id:
                        continue
                    try:
                        payload = self.build_update_payload(row)
                        if not payload:
                            self.log(f"行{idx}: 更新対象なしのためスキップ (id={issue_id})")
                            continue
                        client.update_issue(int(issue_id), payload)
                        ok_count += 1
                        self.log(f"行{idx}: 更新成功 (id={issue_id})")
                    except Exception as row_error:
                        ng_count += 1
                        self.log(f"行{idx}: 更新失敗 (id={issue_id}) {row_error}")
                        errors.append({"line_no": idx, "id": issue_id, "error": str(row_error)})
            if errors:
                err_path = Path(self.export_path_var.get().strip() or EXPORT_DIR) / f"import_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                with err_path.open("w", newline="", encoding="utf-8-sig") as ef:
                    writer = csv.DictWriter(ef, fieldnames=["line_no", "id", "error"])
                    writer.writeheader()
                    writer.writerows(errors)
                self.log(f"エラー一覧を保存しました: {err_path}")
            messagebox.showinfo(APP_NAME, f"インポート完了\n成功: {ok_count}\n失敗: {ng_count}")
        except Exception as e:
            self.log(f"CSVインポート失敗: {e}")
            messagebox.showerror(APP_NAME, f"CSVインポートに失敗しました。\n{e}")

    def build_update_payload(self, row: Dict[str, str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for field in ALLOWED_UPDATE_FIELDS:
            value = (row.get(field) or "").strip()
            if value == "":
                continue
            caster = UPDATE_FIELD_CASTS.get(field)
            payload[field] = caster(value) if caster else value

        notes = (row.get("notes_append") or "").strip()
        if notes:
            payload["notes"] = notes

        desc_append = (row.get("description_append") or "")
        desc_base = (row.get("description") or "")
        if desc_append.strip():
            if desc_base.strip():
                payload["description"] = f"{desc_base.rstrip()}\n\n{desc_append.strip()}"
            else:
                payload["description"] = desc_append.strip()

        return payload

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{stamp}] {message}\n")
        self.log_text.see(tk.END)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
