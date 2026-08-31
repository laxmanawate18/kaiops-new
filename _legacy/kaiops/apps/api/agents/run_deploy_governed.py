"""Detached runner for deploy_governed.py. Writes to a log file. Usage:
python run_deploy_governed.py <engine>
"""
import os, sys, subprocess, traceback, time

ENGINE = sys.argv[1] if len(sys.argv) > 1 else "orchestrator"
LOG = rf"f:\Personal\AI-Project\kaiops_latest\deploy_governed_{ENGINE}.log"
SCRIPT = r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api\agents\deploy_governed.py"
PY = r"f:\Personal\AI-Project\kaiops_latest\.venv\Scripts\python.exe"

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(m + "\n")
    print(m, flush=True)

def main():
    open(LOG, "w", encoding="utf-8").close()
    # Option: pass --no-gateway to deploy identity-only (no gateway binding).
    NO_GATEWAY = "--no-gateway" in sys.argv
    args = [PY, SCRIPT, ENGINE] + (["--no-gateway"] if NO_GATEWAY else [])
    # Run deploy_governed as a subprocess, streaming its output into this log
    proc = subprocess.Popen(
        args,
        cwd=r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api\agents",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ,
    )
    log(f"started deploy [{ENGINE}] pid={proc.pid}")
    for line in proc.stdout:
        log(line.rstrip())
    rc = proc.wait()
    log(f"[{ENGINE}] process exit rc={rc}")
    log("DONE")

if __name__ == "__main__":
    main()
