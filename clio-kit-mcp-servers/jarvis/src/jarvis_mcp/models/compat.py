"""Compatibility adapter over the current JARVIS-CD ``Jarvis`` singleton."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Optional


class _CurrentJarvisManager:
    """Compatibility adapter over the current JARVIS-CD Jarvis singleton."""

    @classmethod
    def get_instance(cls) -> "_CurrentJarvisManager":
        jarvis_module = importlib.import_module("jarvis_cd.core.config")
        return cls(jarvis_module.Jarvis.get_instance())

    def __init__(self, jarvis: Any) -> None:
        self.jarvis = jarvis

    def create(
        self, config_dir: str, private_dir: str, shared_dir: Optional[str] = None
    ) -> "_CurrentJarvisManager":
        self.jarvis.initialize(
            config_dir=config_dir,
            private_dir=private_dir,
            shared_dir=shared_dir or private_dir,
        )
        return self

    def load(self) -> "_CurrentJarvisManager":
        _ = self.jarvis.config
        return self

    def save(self) -> "_CurrentJarvisManager":
        if getattr(self.jarvis, "_config", None) is not None:
            self.jarvis.save_config(self.jarvis.config)
        if getattr(self.jarvis, "_repos", None) is not None:
            self.jarvis.save_repos(self.jarvis.repos)
        return self

    def set_hostfile(self, path: str) -> "_CurrentJarvisManager":
        self.jarvis.set_hostfile(path)
        return self

    def bootstrap_from(self, machine: str) -> "_CurrentJarvisManager":
        raise NotImplementedError(
            f"bootstrap templates are not exposed by current JARVIS-CD: {machine}"
        )

    def bootstrap_list(self) -> list[str]:
        return []

    def reset(self) -> "_CurrentJarvisManager":
        raise NotImplementedError(
            "reset is not exposed through the compatibility adapter"
        )

    def list_pipelines(self) -> list[str]:
        pipelines_dir = self.jarvis.get_pipelines_dir()
        if not pipelines_dir.exists():
            return []
        return sorted(path.name for path in pipelines_dir.iterdir() if path.is_dir())

    def cd(self, pipeline_id: str) -> "_CurrentJarvisManager":
        self.jarvis.set_current_pipeline(pipeline_id)
        return self

    def list_repos(self) -> list[str]:
        return list(self.jarvis.repos.get("repos", []))

    def add_repo(self, path: str, force: bool = False) -> "_CurrentJarvisManager":
        self.jarvis.add_repo(path, force=force)
        return self

    def remove_repo(self, repo_name: str) -> "_CurrentJarvisManager":
        repo_paths = list(self.jarvis.repos.get("repos", []))
        matches = [
            repo_path
            for repo_path in repo_paths
            if repo_path == repo_name or Path(repo_path).name == repo_name
        ]
        if not matches:
            self.jarvis.remove_repo(repo_name)
        for repo_path in matches:
            self.jarvis.remove_repo(repo_path)
        return self

    def promote_repo(self, repo_name: str) -> "_CurrentJarvisManager":
        repos = self.jarvis.repos.copy()
        repo_paths = list(repos.get("repos", []))
        matches = [
            repo_path
            for repo_path in repo_paths
            if repo_path == repo_name or Path(repo_path).name == repo_name
        ]
        if not matches:
            raise ValueError(f"repository not found: {repo_name}")
        for repo_path in reversed(matches):
            repo_paths.remove(repo_path)
            repo_paths.insert(0, repo_path)
        repos["repos"] = repo_paths
        self.jarvis.save_repos(repos)
        return self

    def get_repo(self, repo_name: str) -> dict[str, Any] | None:
        for index, repo_path in enumerate(self.jarvis.repos.get("repos", []), start=1):
            if repo_path == repo_name or Path(repo_path).name == repo_name:
                return {
                    "index": index,
                    "name": Path(repo_path).name,
                    "path": repo_path,
                    "exists": Path(repo_path).exists(),
                }
        return None

    def construct_pkg(self, pkg_type: str) -> Any:
        raise NotImplementedError(
            f"package construction is not exposed by current JARVIS-CD: {pkg_type}"
        )

    def resource_graph_show(self) -> dict[str, Any]:
        return self.jarvis.resource_graph

    def resource_graph_build(self, net_sleep: float) -> dict[str, Any]:
        _ = net_sleep
        raise NotImplementedError(
            "resource graph build is not exposed through the compatibility adapter"
        )

    def resource_graph_modify(self, net_sleep: float) -> dict[str, Any]:
        _ = net_sleep
        raise NotImplementedError(
            "resource graph modify is not exposed through the compatibility adapter"
        )


def _load_jarvis_manager_class() -> Any:
    try:
        module = importlib.import_module("jarvis_cd.basic.jarvis_manager")
        return module.JarvisManager
    except ModuleNotFoundError:
        return _CurrentJarvisManager
