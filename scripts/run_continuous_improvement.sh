#!/bin/bash
# Continuous Improvement Runner
# Runs continuous improvement loop with nohup for long-running workflows

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
LOG_DIR="${PROJECT_ROOT}/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/continuous_improvement_${TIMESTAMP}.log"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# Main execution
main() {
    log "=== Starting Continuous Improvement Loop ==="
    log "Project root: ${PROJECT_ROOT}"
    log "Log file: ${LOG_FILE}"

    cd "${PROJECT_ROOT}"

    # Run with nohup in background
    log "Starting continuous improvement with workflow execution..."
    nohup uv run python scripts/continuous_improvement.py --run-workflow >> "${LOG_FILE}" 2>&1 &

    PID=$!
    log "✅ Process started with PID: ${PID}"
    log "Monitor progress: tail -f ${LOG_FILE}"
    log "Check status: ps aux | grep ${PID}"

    echo ""
    echo "Continuous improvement loop started in background"
    echo "PID: ${PID}"
    echo "Log: ${LOG_FILE}"
    echo ""
    echo "To monitor: tail -f ${LOG_FILE}"
    echo "To stop: kill ${PID}"
}

# Run main function
main "$@"
