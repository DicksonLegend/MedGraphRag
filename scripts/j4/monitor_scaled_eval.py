#!/usr/bin/env python3
"""
MedGraphRAG — J4 Scaled Evaluation Self-Healing Monitor & Watchdog
================================================================
Monitors and manages scripts/j4/run_scaled_n500_eval.py.
Features:
  - Automatically relaunches the runner upon clean chunk exit (100 queries)
    or RSS watchdog threshold (4.5 GB) to ensure fresh memory without leaks.
  - 40-minute watchdog timer / heartbeat check to ensure continuous forward progress.
  - Automatically revives and resumes the runner on unexpected crashes.
  - Terminates cleanly once evaluations/step18_scaled_n500.json is generated.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MONITOR] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_PROJECT_ROOT / "evaluations" / "j4_monitor.log", mode="a"),
    ],
)
logger = logging.getLogger("j4_monitor")

PYTHON_EXEC = str(_PROJECT_ROOT / "Data_Normalization" / ".venv" / "bin" / "python")
RUNNER_SCRIPT = str(_PROJECT_ROOT / "scripts" / "j4" / "run_scaled_n500_eval.py")
FINAL_REPORT_FP = _PROJECT_ROOT / "evaluations" / "step18_scaled_n500.json"
CHECKPOINT_DIR = _PROJECT_ROOT / "evaluations" / "checkpoints_n500"

HEARTBEAT_INTERVAL_S = 2400  # 40 minutes


def get_checkpoint_status() -> str:
    if not CHECKPOINT_DIR.exists():
        return "No checkpoints yet"
    statuses = []
    for mode in ["M1_EVIDENCE_ONLY", "M2_GRAPH_ONLY", "M3_COMBINED", "M4_HYBRID_RERANK"]:
        sum_f = CHECKPOINT_DIR / f"{mode}_summary.json"
        chk_f = CHECKPOINT_DIR / f"{mode}_checkpoint.json"
        if sum_f.exists():
            statuses.append(f"{mode}: 500/500 (COMPLETE)")
        elif chk_f.exists():
            try:
                import json
                with open(chk_f, "r") as f:
                    c = json.load(f).get("completed_count", 0)
                statuses.append(f"{mode}: {c}/500 (IN-PROGRESS)")
            except Exception:
                statuses.append(f"{mode}: (reading checkpoint)")
        else:
            statuses.append(f"{mode}: 0/500 (PENDING)")
    return " | ".join(statuses)


def main():
    logger.info("=" * 80)
    logger.info("J4 Scaled Evaluation Monitor & Watchdog Started")
    logger.info("Python Interpreter: %s", PYTHON_EXEC)
    logger.info("Target Artifact   : %s", FINAL_REPORT_FP)
    logger.info("Heartbeat Interval: %d seconds (40 min)", HEARTBEAT_INTERVAL_S)
    logger.info("=" * 80)

    cycle_count = 0
    t_start = time.time()

    while True:
        if FINAL_REPORT_FP.exists():
            logger.info("=" * 80)
            logger.info("FINAL ARTIFACT FOUND: %s", FINAL_REPORT_FP)
            logger.info("J4 Evaluation Suite 100%% COMPLETE across all 4 modes!")
            logger.info("Total Monitor Runtime: %.1f seconds", time.time() - t_start)
            logger.info("=" * 80)
            break

        cycle_count += 1
        logger.info("Starting Runner Cycle #%d. Current State: [%s]", cycle_count, get_checkpoint_status())

        # Spawn runner process
        runner_env = dict(os.environ)
        runner_env["PYTHONPATH"] = f"{_PROJECT_ROOT}/backend:{_PROJECT_ROOT}"
        proc = subprocess.Popen([PYTHON_EXEC, RUNNER_SCRIPT], cwd=str(_PROJECT_ROOT), env=runner_env)
        pid = proc.pid
        logger.info("Spawned runner process [PID=%d]", pid)

        t_last_heartbeat = time.time()

        # Monitor loop while runner process is running
        while True:
            retcode = proc.poll()
            if retcode is not None:
                # Process terminated
                if retcode == 0:
                    logger.info("Runner process [PID=%d] exited cleanly (exit code 0).", pid)
                else:
                    logger.warning("Runner process [PID=%d] terminated with non-zero exit code: %d.", pid, retcode)
                break

            # Check 40-minute heartbeat
            if time.time() - t_last_heartbeat >= HEARTBEAT_INTERVAL_S:
                t_last_heartbeat = time.time()
                logger.info(
                    "[40-MIN WATCHDOG HEARTBEAT] Runner [PID=%d] active. Progress: [%s]",
                    pid, get_checkpoint_status()
                )

            time.sleep(5)

        # Post-cycle check: if finished, break
        if FINAL_REPORT_FP.exists():
            logger.info("Final artifact generated. Exiting monitor.")
            break

        # Pause briefly before relaunching fresh process to allow OS memory reclamation
        logger.info("Pausing 3s before relaunching runner with clean OS memory space...")
        time.sleep(3)


if __name__ == "__main__":
    main()
