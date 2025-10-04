#!/bin/bash
# Daily YouTube Automation Runner
# Runs the daily workflow and logs results

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
OUTPUT_DIR="${SCRIPT_DIR}/output"
VENV_DIR="${SCRIPT_DIR}/.venv"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/daily_run_${TIMESTAMP}.log"

# Ensure directories exist
mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Main execution
main() {
    log "=== Starting Daily YouTube Automation ==="
    log "Script directory: ${SCRIPT_DIR}"
    log "Log file: ${LOG_FILE}"

    # Check if virtual environment exists
    if [ ! -d "${VENV_DIR}" ]; then
        error_exit "Virtual environment not found at ${VENV_DIR}"
    fi

    # Activate virtual environment
    log "Activating virtual environment..."
    source "${VENV_DIR}/bin/activate" || error_exit "Failed to activate virtual environment"

    # Check .env file
    if [ ! -f "${SCRIPT_DIR}/.env" ]; then
        error_exit ".env file not found"
    fi

    # Run the workflow
    log "Starting daily workflow..."
    cd "${SCRIPT_DIR}"

    if uv run python3 -m app.main daily >> "${LOG_FILE}" 2>&1; then
        log "✅ Daily workflow completed successfully"
        exit 0
    else
        log "❌ Daily workflow failed with exit code $?"
        exit 1
    fi
}

# Run main function
main "$@"
