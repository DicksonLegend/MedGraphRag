#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_EXEC="${PROJECT_ROOT}/Data_Normalization/.venv/bin/python"

echo "================================================================="
echo "Launching MedGraphRAG J4 Scaled N=500 Evaluation under Watchdog"
echo "Project Root: ${PROJECT_ROOT}"
echo "Python Exec : ${PYTHON_EXEC}"
echo "================================================================="

cd "${PROJECT_ROOT}"
exec "${PYTHON_EXEC}" "${SCRIPT_DIR}/monitor_scaled_eval.py"
