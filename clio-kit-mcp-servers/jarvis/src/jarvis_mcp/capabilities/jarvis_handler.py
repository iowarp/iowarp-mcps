import json
import inspect
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

try:  # pragma: no cover - legacy JARVIS-CD environments.
    from jarvis_cd.basic.pkg import Pipeline  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - current JARVIS-CD environments.
    from jarvis_cd.core.pipeline import Pipeline  # type: ignore[import-untyped]


async def create_pipeline(pipeline_id: str) -> dict:
    try:
        pipeline = Pipeline()
        _create_pipeline(pipeline, pipeline_id)
        _build_pipeline_env(pipeline)
        _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create failed: {e}")


async def load_pipeline(pipeline_id: Optional[str] = None) -> dict:
    try:
        _load_pipeline(pipeline_id)
        return {"pipeline_id": pipeline_id, "status": "loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load failed: {e}")


async def export_pipeline(pipeline_id: str, include_yaml: bool = True) -> dict:
    """Return a structured snapshot of a JARVIS pipeline."""
    try:
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
        pipeline = _load_pipeline(pipeline_id)
        pipeline.update()
        _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


async def configure_pkg(pipeline_id: str, pkg_id: str, **kwargs: Any) -> dict:
    try:
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
        pipeline = _load_pipeline(pipeline_id)
        if hasattr(pipeline, "remove"):
            pipeline.remove(pkg_id)
        else:
            pipeline.rm(pkg_id)
        _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "removed": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remove failed: {e}")


async def run_pipeline(pipeline_id: str) -> dict:
    try:
        pipeline = _load_pipeline(pipeline_id)
        pipeline.run()
        return {"pipeline_id": pipeline_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Run failed: {e}")


async def destroy_pipeline(pipeline_id: str) -> dict:
    try:
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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _load_pipeline(pipeline_id: str | None) -> Any:
    if _uses_current_pipeline_api():
        if pipeline_id is not None:
            return Pipeline(pipeline_id)
        pipeline = Pipeline()
        loaded = pipeline.load()
        return loaded if loaded is not None else pipeline
    pipeline = Pipeline()
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
    parameters = inspect.signature(Pipeline.load).parameters
    return "load_type" in parameters
