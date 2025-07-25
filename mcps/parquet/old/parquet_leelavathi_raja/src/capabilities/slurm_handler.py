import subprocess
import pathlib

def submit_slurm_job(script_path, core_count):
    if not script_path or not pathlib.Path(script_path).exists():
        return JSONResponse(
            content={"error": "Invalid or missing SLURM job script path"},
            status_code=400
        )
    submission_msg = subprocess.run(
        ["echo", f"Job submitted: {script_path} with {core_count} cores"],
        capture_output=True,
        text=True
    )

    # Generate a mock job ID based on a hash
    mock_job_id = f"MockJob-{hash(script_path) % 10000}"

    return f"{submission_msg.stdout.strip()} | Mock Job ID: {mock_job_id}"
