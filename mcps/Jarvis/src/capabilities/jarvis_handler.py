from fastapi import HTTPException
from jarvis_cd.basic.pkg import Pipeline
import os

async def create_pipeline(pipeline_id: str) -> dict:
    try:
        Pipeline().create(pipeline_id).build_env().save()
        return {"pipeline_id": pipeline_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create failed: {e}")

async def load_pipeline(pipeline_id: str = None) -> dict:
    try:
        pipeline = Pipeline().load(pipeline_id)
        return {"pipeline_id": pipeline_id, "status": "loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load failed: {e}")

async def append_pkg(
    pipeline_id: str,
    pkg_type: str,
    pkg_id: str = None,
    do_configure: bool = True,
    **kwargs
) -> dict:
    try:
        # Avoid duplicate do_configure in kwargs
        raw_kwargs = dict(kwargs)
        config_flag = do_configure
        if 'do_configure' in raw_kwargs:
            config_flag = raw_kwargs.pop('do_configure')

        pipeline = Pipeline().load(pipeline_id)
        pipeline.append(
            pkg_type,
            pkg_id=pkg_id,
            do_configure=config_flag,
            **raw_kwargs
        ).save()
        return {"pipeline_id": pipeline_id, "appended": pkg_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Append failed: {e}")


async def build_pipeline_env(pipeline_id: str) -> dict:
    """
    Load a Jarvis-CD pipeline, rebuild its environment cache,
    tracking only CMAKE_PREFIX_PATH and PATH from the current shell, then save.
    """
    try:
        # 1. Load the existing pipeline
        pipeline = Pipeline().load(pipeline_id)

        # 2. Always track these two vars
        default_keys = ["CMAKE_PREFIX_PATH", "PATH"]
        env_track_dict = {key: True for key in default_keys}

        # 3. Rebuild the env cache, track only those vars, and save
        pipeline.build_env(env_track_dict).save()

        return {
            "pipeline_id": pipeline_id,
            "status": "environment_built"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build env failed: {e}")


async def update_pipeline(pipeline_id: str) -> dict:
    """
    Re-apply the current environment & configuration to every pkg in the pipeline,
    then persist the updated pipeline.
    """
    try:
        pipeline = Pipeline().load(pipeline_id)
        pipeline.update()  # re-run configure on all sub-pkgs
        pipeline.save()    # persist any changes
        return {"pipeline_id": pipeline_id, "status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


async def configure_pkg(pipeline_id: str, pkg_id: str, **kwargs) -> dict:
    try:
        pipeline = Pipeline().load(pipeline_id)
        # configure the pkg (this does NOT return self)
        pipeline.configure(pkg_id, **kwargs)

        # now save the entire pipeline (which will recurse and save each sub-pkg)
        pipeline.save()
        return {"pipeline_id": pipeline_id, "configured": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configure failed: {e}")

async def get_pkg_config(pipeline_id: str, pkg_id: str) -> dict:
    try:
        # 1. Load the pipeline
        pipeline = Pipeline().load(pipeline_id)

        # 2. Lookup the pkg
        pkg = pipeline.get_pkg(pkg_id)
        if pkg is None:
            raise HTTPException(status_code=404, detail=f"Package '{pkg_id}' not found")

        # 3. Return its config dict
        return {
            "pipeline_id": pipeline.global_id,
            "pkg_id": pkg_id,
            "config": pkg.config
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get config failed: {e}")

async def unlink_pkg(pipeline_id: str, pkg_id: str) -> dict:
    try:
        Pipeline().load(pipeline_id).unlink(pkg_id).save()
        return {"pipeline_id": pipeline_id, "unlinked": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unlink failed: {e}")

async def remove_pkg(pipeline_id: str, pkg_id: str) -> dict:
    try:
        Pipeline().load(pipeline_id).remove(pkg_id).save()
        return {"pipeline_id": pipeline_id, "removed": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remove failed: {e}")

async def run_pipeline(pipeline_id: str) -> dict:
    try:
        Pipeline().load(pipeline_id).run()
        return {"pipeline_id": pipeline_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Run failed: {e}")

async def destroy_pipeline(pipeline_id: str) -> dict:
    try:
        Pipeline().load(pipeline_id).destroy()
        return {"pipeline_id": pipeline_id, "status": "destroyed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Destroy failed: {e}")