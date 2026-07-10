import json
import inspect
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

Pipeline: Any | None = None
_PIPELINE_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - current JARVIS-CD environments.
    from jarvis_cd.core.pipeline import Pipeline as _Pipeline  # type: ignore[import-untyped]

    Pipeline = _Pipeline
except ModuleNotFoundError as core_error:  # pragma: no cover - legacy environments.
    try:
        from jarvis_cd.basic.pkg import Pipeline as _Pipeline  # type: ignore[import-untyped]

        Pipeline = _Pipeline
    except ModuleNotFoundError as legacy_error:
        _PIPELINE_IMPORT_ERROR = (
            legacy_error if "jarvis_cd" in str(legacy_error) else core_error
        )


async def create_pipeline(pipeline_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _require_pipeline_class()()
            _create_pipeline(pipeline, pipeline_id)
            _build_pipeline_env(pipeline)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create failed: {e}")


async def configure_pipeline(pipeline_id: str, config: dict[str, Any]) -> dict:
    """Configure pipeline-level JARVIS settings using native Pipeline fields."""
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            _apply_pipeline_config(pipeline, config)
            _save_pipeline(pipeline)
        return {
            "pipeline_id": _pipeline_id(pipeline),
            "status": "configured",
            "config": _jsonable(_pipeline_config(pipeline)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline configure failed: {e}")


async def load_pipeline(pipeline_id: Optional[str] = None) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            _load_pipeline(pipeline_id)
        return {"pipeline_id": pipeline_id, "status": "loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load failed: {e}")


async def export_pipeline(pipeline_id: str, include_yaml: bool = True) -> dict:
    """Return a structured snapshot of a JARVIS pipeline."""
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            config = _pipeline_config(pipeline)
        yaml_path = _optional_str(config.get("JARVIS_YAML_PATH"))
        payload: dict[str, Any] = {
            "pipeline_id": _pipeline_id(pipeline),
            "config_path": _optional_str(_pipeline_config_path(pipeline)),
            "env_path": _optional_str(_pipeline_env_path(pipeline)),
            "yaml_path": yaml_path,
            "config": _jsonable(config),
            "env": _jsonable(getattr(pipeline, "env", {})),
            "packages": [
                _package_snapshot(pkg) for pkg in _pipeline_packages(pipeline)
            ],
        }
        if include_yaml and yaml_path is not None:
            yaml_file = Path(yaml_path)
            if yaml_file.exists():
                payload["pipeline_yaml"] = yaml_file.read_text(encoding="utf-8")
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


async def append_pkg(
    pipeline_id: str,
    pkg_type: str,
    pkg_id: Optional[str] = None,
    do_configure: bool = True,
    **kwargs: Any,
) -> dict:
    try:
        raw_kwargs = dict(kwargs)
        config_flag = do_configure
        if "do_configure" in raw_kwargs:
            config_flag = raw_kwargs.pop("do_configure")

        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if _is_legacy_pipeline(pipeline):
                pipeline.append(
                    pkg_type, pkg_id=pkg_id, do_configure=config_flag, **raw_kwargs
                ).save()
            else:
                config_args = _kwargs_to_config_args(raw_kwargs)
                if config_flag is not None:
                    config_args.append(f"do_configure={str(config_flag).lower()}")
                pipeline.append(pkg_type, package_alias=pkg_id, config_args=config_args)
                _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "appended": pkg_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Append failed: {e}")


async def build_pipeline_env(pipeline_id: str) -> dict:
    """
    Load a Jarvis-CD pipeline, rebuild its environment cache,
    tracking only CMAKE_PREFIX_PATH and PATH from the current shell, then save.
    """
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            _build_pipeline_env(pipeline)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "environment_built"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build env failed: {e}")


async def update_pipeline(pipeline_id: str) -> dict:
    """
    Re-apply the current environment & configuration to every pkg in the pipeline,
    then persist the updated pipeline.
    """
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            pipeline.update()
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


async def configure_pkg(pipeline_id: str, pkg_id: str, **kwargs: Any) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if hasattr(pipeline, "configure"):
                pipeline.configure(pkg_id, **kwargs)
            else:
                pipeline.configure_package(pkg_id, _kwargs_to_config_args(kwargs))
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "configured": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configure failed: {e}")


async def get_pkg_config(pipeline_id: str, pkg_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            pkg = _get_package(pipeline, pkg_id)
        if pkg is None:
            raise HTTPException(status_code=404, detail=f"Package '{pkg_id}' not found")
        return {
            "pipeline_id": _pipeline_id(pipeline),
            "pkg_id": pkg_id,
            "config": _jsonable(_package_config(pkg)),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get config failed: {e}")


async def unlink_pkg(pipeline_id: str, pkg_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if hasattr(pipeline, "unlink"):
                pipeline.unlink(pkg_id)
            else:
                pipeline.rm(pkg_id)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "unlinked": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unlink failed: {e}")


async def remove_pkg(pipeline_id: str, pkg_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if hasattr(pipeline, "remove"):
                pipeline.remove(pkg_id)
            else:
                pipeline.rm(pkg_id)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "removed": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remove failed: {e}")


async def run_pipeline(
    pipeline_id: str,
    mode: str = "auto",
    *,
    submit: bool = True,
    wait: bool = False,
) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            normalized = mode.strip().lower()
            if normalized not in {"auto", "direct", "scheduler"}:
                raise ValueError("mode must be one of: auto, direct, scheduler")
            scheduler = getattr(pipeline, "scheduler", None)
            has_scheduler = isinstance(scheduler, dict) and bool(scheduler)
            if normalized == "scheduler" or (normalized == "auto" and has_scheduler):
                script_path = pipeline.submit(submit=submit, wait=wait)
                return {
                    "pipeline_id": _pipeline_id(pipeline) or pipeline_id,
                    "status": "submitted" if submit else "scripted",
                    "mode": "scheduler",
                    "scheduler": _jsonable(scheduler),
                    "script_path": str(script_path),
                    "wait": wait,
                }
            pipeline.run()
            return {
                "pipeline_id": _pipeline_id(pipeline) or pipeline_id,
                "status": "running",
                "mode": "direct",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Run failed: {e}")


async def destroy_pipeline(pipeline_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            pipeline.destroy()
        return {"pipeline_id": pipeline_id, "status": "destroyed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Destroy failed: {e}")


def _package_snapshot(pkg: Any) -> dict[str, Any]:
    if isinstance(pkg, dict):
        return {
            "pkg_id": _optional_str(pkg.get("pkg_id") or pkg.get("id")),
            "pkg_type": _optional_str(pkg.get("pkg_type") or pkg.get("type")),
            "global_id": _optional_str(pkg.get("global_id")),
            "config_path": _optional_str(pkg.get("config_path")),
            "config": _jsonable(pkg.get("config")),
        }
    return {
        "pkg_id": _optional_str(getattr(pkg, "pkg_id", None)),
        "pkg_type": _optional_str(getattr(pkg, "pkg_type", None)),
        "global_id": _optional_str(getattr(pkg, "global_id", None)),
        "config_path": _optional_str(getattr(pkg, "config_path", None)),
        "config": _jsonable(getattr(pkg, "config", None)),
    }


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [_jsonable(item) for item in value]
        return repr(value)


def _protocol_stdout_to_stderr() -> Any:
    """Keep JARVIS package prints off stdio MCP stdout."""
    return redirect_stdout(sys.stderr)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _load_pipeline(pipeline_id: str | None) -> Any:
    pipeline_cls = _require_pipeline_class()
    if _uses_current_pipeline_api():
        if pipeline_id is not None:
            return pipeline_cls(pipeline_id)
        pipeline = pipeline_cls()
        loaded = pipeline.load()
        return loaded if loaded is not None else pipeline
    pipeline = pipeline_cls()
    loaded = pipeline.load(pipeline_id)
    return loaded if loaded is not None else pipeline


def _create_pipeline(pipeline: Any, pipeline_id: str) -> Any:
    created = pipeline.create(pipeline_id)
    return created if created is not None else pipeline


def _save_pipeline(pipeline: Any) -> None:
    if hasattr(pipeline, "save"):
        pipeline.save()


def _build_pipeline_env(pipeline: Any) -> None:
    if not hasattr(pipeline, "build_env"):
        return
    default_keys = ["CMAKE_PREFIX_PATH", "PATH"]
    env_track_dict = {key: True for key in default_keys}
    try:
        built = pipeline.build_env(env_track_dict)
    except TypeError:
        built = pipeline.build_env()
    if built is not None and built is not pipeline:
        _save_pipeline(built)


def _apply_pipeline_config(pipeline: Any, config: dict[str, Any]) -> None:
    """Apply top-level Pipeline configuration that JARVIS persists to YAML."""
    supported = {
        "scheduler",
        "hostfile",
        "hostfile_entries",
        "container_image",
        "container_uri",
        "container_engine",
        "container_base",
        "container_ssh_port",
        "container_extensions",
        "container_env",
        "container_host_path",
        "container_workspace",
        "container_caps",
        "container_binds",
        "container_gpu",
        "tmp_bind_root",
        "base_deploy_mode",
        "ssh_cmd",
        "pssh_cmd",
        "mpi_cmd",
        "env",
    }
    unknown = sorted(set(config) - supported)
    if unknown:
        raise ValueError(f"unsupported pipeline config keys: {', '.join(unknown)}")
    if "scheduler" in config:
        scheduler = config["scheduler"]
        if scheduler is not None and not isinstance(scheduler, dict):
            raise ValueError("scheduler must be an object or null")
        pipeline.scheduler = dict(scheduler) if scheduler is not None else None
        if pipeline.scheduler and hasattr(pipeline, "_apply_scheduler_hostfile"):
            pipeline._apply_scheduler_hostfile()
    if "hostfile" in config:
        hostfile_path = config["hostfile"]
        if hostfile_path in (None, ""):
            pipeline.hostfile = None
        else:
            from jarvis_cd.util.hostfile import Hostfile  # type: ignore[import-untyped]

            pipeline.hostfile = Hostfile(path=str(hostfile_path))
    if "hostfile_entries" in config:
        hosts = config["hostfile_entries"]
        if not isinstance(hosts, list) or not all(
            isinstance(host, str) for host in hosts
        ):
            raise ValueError("hostfile_entries must be a list of host names")
        shared_dir = pipeline.jarvis.get_pipeline_shared_dir(pipeline.name)
        shared_dir.mkdir(parents=True, exist_ok=True)
        hostfile_path = shared_dir / "mcp-hostfile.txt"
        hostfile_path.write_text("\n".join(hosts) + "\n", encoding="utf-8")
        from jarvis_cd.util.hostfile import Hostfile  # type: ignore[import-untyped]

        pipeline.hostfile = Hostfile(path=str(hostfile_path))
    if "env" in config:
        env = config["env"]
        if env is None:
            pipeline.env = {}
        elif isinstance(env, dict):
            pipeline.env.update(env)
        else:
            raise ValueError("env must be an object or null")
    for key in supported - {"scheduler", "hostfile", "hostfile_entries", "env"}:
        if key in config:
            setattr(pipeline, key, config[key])
    if hasattr(pipeline, "_apply_launcher_overrides"):
        pipeline._apply_launcher_overrides()


def _is_legacy_pipeline(pipeline: Any) -> bool:
    return hasattr(pipeline, "sub_pkgs") or hasattr(pipeline, "configure")


def _pipeline_id(pipeline: Any) -> str | None:
    return _optional_str(
        getattr(pipeline, "global_id", None)
        or getattr(pipeline, "pipeline_id", None)
        or getattr(pipeline, "name", None)
    )


def _pipeline_config(pipeline: Any) -> dict[str, Any]:
    config = getattr(pipeline, "config", None)
    if isinstance(config, dict):
        return config
    data: dict[str, Any] = {
        "name": getattr(pipeline, "name", None),
        "packages": _pipeline_packages(pipeline),
        "interceptors": getattr(pipeline, "interceptors", None),
        "scheduler": getattr(pipeline, "scheduler", None),
        "hostfile": getattr(pipeline, "hostfile", None),
    }
    return {key: value for key, value in data.items() if value is not None}


def _pipeline_config_path(pipeline: Any) -> Any:
    if hasattr(pipeline, "config_path"):
        return getattr(pipeline, "config_path")
    jarvis = getattr(pipeline, "jarvis", None)
    name = getattr(pipeline, "name", None)
    if jarvis is not None and name and hasattr(jarvis, "get_pipeline_dir"):
        return jarvis.get_pipeline_dir(name) / "pipeline.yaml"
    return None


def _pipeline_env_path(pipeline: Any) -> Any:
    if hasattr(pipeline, "env_path"):
        return getattr(pipeline, "env_path")
    jarvis = getattr(pipeline, "jarvis", None)
    name = getattr(pipeline, "name", None)
    if jarvis is not None and name and hasattr(jarvis, "get_pipeline_dir"):
        return jarvis.get_pipeline_dir(name) / "environment.yaml"
    return None


def _pipeline_packages(pipeline: Any) -> list[Any]:
    packages = getattr(pipeline, "sub_pkgs", None)
    if packages is None:
        packages = getattr(pipeline, "packages", [])
    return list(packages)


def _get_package(pipeline: Any, pkg_id: str) -> Any:
    if hasattr(pipeline, "get_pkg"):
        return pipeline.get_pkg(pkg_id)
    for pkg in _pipeline_packages(pipeline):
        if isinstance(pkg, dict):
            if pkg.get("pkg_id") == pkg_id or pkg.get("id") == pkg_id:
                return pkg
        elif getattr(pkg, "pkg_id", None) == pkg_id:
            return pkg
    return None


def _package_config(pkg: Any) -> Any:
    if isinstance(pkg, dict):
        return pkg.get("config", {})
    return getattr(pkg, "config", {})


def _kwargs_to_config_args(kwargs: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, bool):
            args.append(f"{key}={str(value).lower()}")
        else:
            args.append(f"{key}={value}")
    return args


def _uses_current_pipeline_api() -> bool:
    pipeline_cls = _require_pipeline_class()
    parameters = inspect.signature(pipeline_cls.load).parameters
    return "load_type" in parameters


def _require_pipeline_class() -> Any:
    if Pipeline is not None:
        return Pipeline
    detail = f": {_PIPELINE_IMPORT_ERROR}" if _PIPELINE_IMPORT_ERROR is not None else ""
    raise RuntimeError(
        "JARVIS-CD Pipeline API is not available. Install a JARVIS-CD version "
        f"with jarvis_cd.core.pipeline or legacy jarvis_cd.basic.pkg{detail}"
    )
