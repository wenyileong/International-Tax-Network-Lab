"""Research Suite integration: A-share releases and suite projects inside the Lab.

The Lab does not have a converter of its own. It runs the Research Suite's shared core (``rscore``, vendored
under ``src/rscore`` and pinned to a commit, see ``scripts/sync_rscore.py``), so that a release of A-share
Company Intelligence is converted in the Lab exactly as ResearchSuite.exe converts it: the same exclusion of
natural persons, the same rejection rules, the same place-name registry and the same review of jurisdictions.

A *suite project* is one SQLite store file with a ``<name>_files`` folder beside it (import reports, the
jurisdiction choices made during review, Lab exports). Projects the Lab creates live in the workspace folder
``suite_projects`` and can be opened in ResearchSuite.exe; projects created by ResearchSuite.exe are found
through its settings file (recent projects) or can be opened by path.

The flow is the suite's: import a release into a project, resolve the names and places that need a
jurisdiction, re-import, then bring the project into the Lab, which exports the Lab's tables and imports them
as a content-addressed dataset whose metadata records where every table came from.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[^\\/:*?\"<>|\x00-\x1f]{1,80}$")
PROJECT_SUFFIXES = (".sqlite", ".db")
#: Rejection reasons and review statuses the suite's importer reports (checked against the vendored code by a test).
REASONS = ("natural_person_excluded", "table_columns_shifted", "stake_missing", "stake_outside_0_100",
           "stakes_sum_over_100", "holder_jurisdiction_needs_review", "place_unmatched", "place_ambiguous",
           "place_missing", "no_direct_stake", "indirect_only", "below_min_confidence", "unknown_jurisdiction_code",
           "consolidation_scope_not_stated", "revenue_missing_or_negative", "revenue_implausibly_small",
           "revenue_candidates_disagree", "observation_date_missing")


class SuiteError(ValueError):
    pass


def vendored() -> dict[str, Any]:
    """Version and source commit of the vendored suite core."""
    import rscore

    from importlib import resources

    info: dict[str, Any] = {"rscore_version": rscore.__version__, "schema_generation": rscore.SCHEMA_GENERATION}
    try:
        meta = json.loads(resources.files("rscore").joinpath("VENDORED.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    info["commit"] = meta.get("commit")
    info["source"] = meta.get("source")
    return info


# ------------------------------------------------------------------ the suite's own settings
def suite_config_path() -> Path:
    """Where ResearchSuite.exe keeps its settings (mirrors ``rscore.launcher.tools.default_config_path``)."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "ResearchSuite" / "launcher.json"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "research-suite" / "launcher.json"


def suite_settings(path: Path | None = None) -> dict[str, Any]:
    """The suite launcher's settings, read only; an absent or damaged file gives an empty result."""
    p = path or suite_config_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def suite_language(path: Path | None = None) -> str | None:
    """The suite's interface language as a Lab locale tag (the suite uses ``en`` and ``zh-Hans``)."""
    lang = suite_settings(path).get("language")
    return {"en": "en-GB", "zh-Hans": "zh-Hans"}.get(lang) if isinstance(lang, str) else None


# ------------------------------------------------------------------ bridge
class SuiteBridge:
    def __init__(self, ws, config_path: Path | None = None):
        self.ws = ws
        self.folder = ws.root / "suite_projects"
        self.known_file = ws.root / "suite_projects.json"
        self.config_path = config_path

    # -------------------------------------------------------------- projects
    def _known(self) -> list[str]:
        try:
            data = json.loads(self.known_file.read_text(encoding="utf-8"))
            return [p for p in data.get("projects", []) if isinstance(p, str)]
        except (OSError, ValueError):
            return []

    def _remember(self, path: Path) -> None:
        known = [str(path)] + [p for p in self._known() if p != str(path)]
        self.known_file.write_text(json.dumps({"projects": known[:30]}, indent=2), encoding="utf-8")

    def project(self, path: str | Path, must_exist: bool = True):
        from rscore import services

        p = Path(str(path)).expanduser()
        if p.suffix.lower() not in PROJECT_SUFFIXES:
            raise SuiteError(f"a suite project is a .sqlite file: {p}")
        p = p.resolve()
        if must_exist and not p.is_file():
            raise KeyError(f"no suite project at {p}")
        return services.Project(p)

    def projects(self) -> list[dict[str, Any]]:
        """Projects in the workspace, projects opened before, and the suite launcher's recent projects."""
        seen: dict[str, dict[str, Any]] = {}

        def add(path: Path, origin: str) -> None:
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                return
            seen[key] = {"path": key, "name": path.stem, "origin": origin, "exists": path.is_file()}

        if self.folder.exists():
            for p in sorted(self.folder.glob("*.sqlite")):
                add(p, "lab")
        for p in self._known():
            add(Path(p), "opened")
        for p in suite_settings(self.config_path).get("recent_projects", []) or []:
            if isinstance(p, str):
                add(Path(p), "suite")
        out = []
        for item in seen.values():
            if item["exists"]:
                try:
                    item.update(self._brief(self.project(item["path"])))
                except Exception as exc:  # a damaged or foreign file is listed, not fatal
                    item["error"] = f"{type(exc).__name__}: {exc}"
            out.append(item)
        return out

    def _brief(self, project) -> dict[str, Any]:
        from rscore import services

        latest = services.latest_report(project)
        exports = sorted((p for p in (project.path.with_name(project.name + "_files") / "lab_exports").glob("*")
                          if p.is_dir()), reverse=True) if project.path.with_name(project.name + "_files").exists() else []
        return {"counts": services.summary(project), "latest_report": latest.name if latest else None,
                "lab_exports": [{"name": p.name, "path": str(p)} for p in exports[:10]]}

    def create_project(self, name: str):
        from rscore import services

        name = (name or "").strip()
        if not NAME_RE.match(name) or name in (".", ".."):
            raise SuiteError("a project name has 1 to 80 characters and none of \\ / : * ? \" < > |")
        self.folder.mkdir(parents=True, exist_ok=True)
        project = services.create_project(self.folder / f"{name}.sqlite")
        self._remember(project.path)
        return project

    def open_project(self, path: str | Path) -> dict[str, Any]:
        project = self.project(path)
        self._remember(project.path)
        return self.detail(project.path)

    def detail(self, path: str | Path) -> dict[str, Any]:
        """Everything the Research Suite page shows for one project: counts, the latest import and its review."""
        from rscore import services

        project = self.project(path)
        out: dict[str, Any] = {"path": str(project.path), "name": project.name, **self._brief(project),
                               "overrides": services.load_overrides(project)}
        latest = services.latest_report(project)
        out["report"] = self._report(project, latest) if latest else None
        return out

    def _report(self, project, report_dir: Path) -> dict[str, Any]:
        from rscore import services

        data = json.loads((report_dir / "import_report.json").read_text(encoding="utf-8"))
        return {"folder": str(report_dir), "name": report_dir.name, "summary": data,
                "settings": services.report_settings(report_dir),
                "review": [vars(r) for r in services.load_review(report_dir, project)],
                "revenue_conflicts": services.load_revenue_conflicts(report_dir)}

    # -------------------------------------------------------------- releases
    @staticmethod
    def inspect_release(folder: str | Path) -> dict[str, Any]:
        """What a release folder holds, read from its manifest, before anything is imported."""
        f = Path(str(folder)).expanduser()
        m_path = f / "manifest.json"
        if not m_path.is_file():
            raise SuiteError(f"{f} has no manifest.json; choose the folder of an A-share Company Intelligence release")
        try:
            m = json.loads(m_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SuiteError(f"manifest.json cannot be read: {exc}") from None
        companies = []
        c_path = f / "csv" / "companies.csv"
        if c_path.is_file():
            with c_path.open(encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    companies.append({"security_code": r.get("security_code"), "short_name": r.get("short_name_cn"),
                                      "name_en": r.get("legal_name_en") or None, "exchange": r.get("exchange")})
        sw = m.get("software") or {}
        return {"folder": str(f.resolve()), "name": m.get("name", f.name), "created_utc": m.get("created_utc"),
                "software": f"{sw.get('name', '')} {sw.get('version', '')}".strip() or None,
                "row_counts": m.get("row_counts") or {}, "citation": m.get("citation"),
                "pseudonymised": bool((m.get("pseudonymisation") or {}).get("applied")),
                "fingerprint": m.get("database_fingerprint"), "companies": companies,
                "tables_present": sorted(p.stem for p in (f / "csv").glob("*.csv")) if (f / "csv").is_dir() else []}

    def import_release(self, project_path: str | Path | None, release: str | Path, *, project_name: str | None = None,
                       companies: list[str] | tuple[str, ...] = (), assume_consolidated: bool = False,
                       accept_suggestions: bool = False, min_confidence: float = 0.0) -> dict[str, Any]:
        """Import a release into a project (created in the workspace when no path is given) with the suite's importer."""
        from rscore import services

        info = self.inspect_release(release)
        if project_path:
            project = self.project(project_path)
            self._remember(project.path)
        else:
            project = self.create_project(project_name or _safe_name(info["name"]))
        try:
            mc = float(min_confidence or 0.0)
        except (TypeError, ValueError):
            raise SuiteError("min_confidence must be a number between 0 and 1") from None
        if not 0.0 <= mc <= 1.0:
            raise SuiteError("min_confidence must be a number between 0 and 1")
        codes = tuple(str(c).strip() for c in companies if str(c).strip())
        services.run_import(project, info["folder"], companies=codes, assume_consolidated=bool(assume_consolidated),
                            accept_suggestions=bool(accept_suggestions), min_confidence=mc)
        return self.detail(project.path)

    def reimport(self, project_path: str | Path) -> dict[str, Any]:
        """Run the latest import again with the same settings, now using the jurisdiction choices saved since."""
        from rscore import services

        project = self.project(project_path)
        latest = services.latest_report(project)
        if not latest:
            raise SuiteError("this project has no import to repeat")
        s = services.report_settings(latest)
        if not s.get("release_folder") or not Path(s["release_folder"]).is_dir():
            raise SuiteError(f"the release folder of the last import is no longer available: {s.get('release_folder')}")
        return self.import_release(project.path, s["release_folder"], companies=s.get("companies") or (),
                                   assume_consolidated=s.get("assume_consolidated", False),
                                   accept_suggestions=s.get("accept_suggestions", False),
                                   min_confidence=s.get("min_confidence", 0.0))

    def save_overrides(self, project_path: str | Path, choices: dict[str, str]) -> dict[str, Any]:
        from rscore import services

        if not isinstance(choices, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in choices.items()):
            raise SuiteError("'choices' must map names to jurisdiction codes")
        project = self.project(project_path)
        services.save_overrides(project, choices)
        return self.detail(project.path)

    @staticmethod
    def jurisdictions() -> list[dict[str, str]]:
        from rscore import services

        return [{"code": k, "name": v} for k, v in sorted(services.jurisdiction_codes().items())]

    # -------------------------------------------------------------- into the Lab
    def bring_into_lab(self, api, project_path: str | Path, name: str | None = None,
                       trim_jurisdictions: bool = True) -> dict[str, Any]:
        """Export the project's Lab tables (suite format) and import them as a Lab dataset with provenance."""
        from rscore import services

        project = self.project(project_path)
        folder = services.export_lab(project)
        return self.import_export_folder(api, folder, name=name, project=project, trim_jurisdictions=trim_jurisdictions)

    def import_export_folder(self, api, folder: str | Path, name: str | None = None, project=None,
                             trim_jurisdictions: bool = True) -> dict[str, Any]:
        from rscore import services

        f = Path(str(folder)).expanduser().resolve()
        if not f.is_dir():
            raise SuiteError(f"no folder at {f}")
        texts = {p.stem: p.read_text(encoding="utf-8-sig") for p in sorted(f.glob("*.csv"))}
        if not texts:
            raise SuiteError(f"{f} holds no table CSV files")
        trimmed = 0
        if trim_jurisdictions and "jurisdictions" in texts:
            texts["jurisdictions"], trimmed = trim_unused_jurisdictions(texts)
        if project is None and f.parent.name == "lab_exports" and f.parent.parent.name.endswith("_files"):
            candidate = f.parent.parent.with_name(f.parent.parent.name[:-len("_files")] + ".sqlite")
            project = services.Project(candidate) if candidate.is_file() else None
        provenance: dict[str, Any] = {"origin": "research_suite", "export_folder": str(f), **vendored(),
                                      "unused_registry_jurisdictions_dropped": trimmed}
        if project is not None:
            provenance["suite_project"] = str(project.path)
            latest = services.latest_report(project)
            if latest:
                data = json.loads((latest / "import_report.json").read_text(encoding="utf-8"))
                provenance["release"] = data.get("release")
                provenance["import_report"] = str(latest)
                provenance["import_settings"] = services.report_settings(latest)
                provenance["review_outstanding"] = data.get("review_jurisdictions", 0)
                provenance["revenue_conflicts"] = data.get("review_revenue", 0)
        label = name or (f"{project.name} (Research Suite)" if project is not None else f"{f.name} (Research Suite)")
        return api.import_csv(label, texts, metadata=provenance)


def trim_unused_jurisdictions(texts: dict[str, str]) -> tuple[str, int]:
    """Keep only the jurisdictions that some row refers to (and their parents).

    A suite export carries the whole jurisdiction registry (some 250 rows). They are reference data, not
    observations, but methods that take every jurisdiction as an observation (persistent homology, the
    jurisdiction matrix) would otherwise be dominated by jurisdictions with no data at all.
    """
    import io

    used: set[str] = set()
    for table, text in texts.items():
        if table == "jurisdictions":
            continue
        for row in csv.DictReader(io.StringIO(text)):
            for col, value in row.items():
                if value and col and (col.endswith("jurisdiction_id") or col.endswith("_jurisdiction")):
                    used.add(value)
    rows = list(csv.DictReader(io.StringIO(texts["jurisdictions"])))
    by_id = {r["jurisdiction_id"]: r for r in rows}
    frontier = list(used)
    while frontier:
        parent = (by_id.get(frontier.pop()) or {}).get("parent_jurisdiction_id")
        if parent and parent not in used:
            used.add(parent)
            frontier.append(parent)
    kept = [r for r in rows if r["jurisdiction_id"] in used]
    buf = io.StringIO()
    header = next(csv.reader(io.StringIO(texts["jurisdictions"])))
    w = csv.DictWriter(buf, fieldnames=header, lineterminator="\n")
    w.writeheader()
    w.writerows(kept)
    return buf.getvalue(), len(rows) - len(kept)


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", text or "").strip(" .") or "A-share release"
    return cleaned[:80]
