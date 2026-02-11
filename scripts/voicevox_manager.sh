#!/bin/bash
# VOICEVOX Nemo サーバー管理スクリプト
# Usage: ./voicevox_manager.sh {start|stop|restart|status|logs}

set -euo pipefail

# 設定（環境変数で上書き可能）
VOICEVOX_PORT="${VOICEVOX_PORT:-50121}"
VOICEVOX_CONTAINER_NAME="${VOICEVOX_CONTAINER_NAME:-voicevox-nemo}"
VOICEVOX_SPEAKER="${VOICEVOX_SPEAKER:-1}"
VOICEVOX_IMAGE="${VOICEVOX_IMAGE:-voicevox/voicevox_engine:cpu-ubuntu20.04-latest}"
VOICEVOX_HEALTHCHECK_PATH="${VOICEVOX_HEALTHCHECK_PATH:-/speakers}"
VOICEVOX_START_TIMEOUT="${VOICEVOX_START_TIMEOUT:-90}"
VOICEVOX_PULL_RETRIES="${VOICEVOX_PULL_RETRIES:-3}"
VOICEVOX_HEALTH_INTERVAL="${VOICEVOX_HEALTH_INTERVAL:-10s}"
VOICEVOX_HEALTH_TIMEOUT="${VOICEVOX_HEALTH_TIMEOUT:-3s}"
VOICEVOX_HEALTH_RETRIES="${VOICEVOX_HEALTH_RETRIES:-5}"
VOICEVOX_HEALTH_START_PERIOD="${VOICEVOX_HEALTH_START_PERIOD:-20s}"
VOICEVOX_CPU_LIMIT="${VOICEVOX_CPU_LIMIT:-}"
VOICEVOX_MEMORY_LIMIT="${VOICEVOX_MEMORY_LIMIT:-}"
VOICEVOX_RESTART_POLICY="${VOICEVOX_RESTART_POLICY:-unless-stopped}"
VOICEVOX_STOP_TIMEOUT="${VOICEVOX_STOP_TIMEOUT:-20}"
LOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/logs"
VOICEVOX_LOG="${LOG_DIR}/voicevox_nemo.log"

# ディレクトリ作成
mkdir -p "${LOG_DIR}"

# ログ関数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${VOICEVOX_LOG}"
}

# ポート競合チェック
check_port_available() {
    if ! command -v python3 >/dev/null 2>&1; then
        log "WARN: python3 not found; skipping port availability check"
        return 0
    fi

    if python3 - <<PY >/dev/null 2>&1; then
import socket
import sys

port = int("${VOICEVOX_PORT}")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    sys.exit(0 if sock.connect_ex(("127.0.0.1", port)) != 0 else 1)
PY
        return 0
    else
        log "ERROR: Port ${VOICEVOX_PORT} is already in use"
        echo "Port ${VOICEVOX_PORT} is already in use. Stop the conflicting service or set VOICEVOX_PORT." >&2
        exit 1
    fi
}

# 画像取得（リトライ付き）
pull_image_with_retry() {
    local attempt=1
    while [ "${attempt}" -le "${VOICEVOX_PULL_RETRIES}" ]; do
        if docker pull "${VOICEVOX_IMAGE}" >> "${VOICEVOX_LOG}" 2>&1; then
            return 0
        fi

        local wait_seconds=$((attempt * 5))
        log "WARN: Failed to pull image (attempt ${attempt}/${VOICEVOX_PULL_RETRIES}). Retrying in ${wait_seconds}s..."
        sleep "${wait_seconds}"
        attempt=$((attempt + 1))
    done

    log "ERROR: Unable to pull ${VOICEVOX_IMAGE} after ${VOICEVOX_PULL_RETRIES} attempts"
    return 1
}

# ヘルスチェック待機
wait_for_health() {
    local start_ts=$(date +%s)

    while true; do
        local state
        state=$(docker inspect --format='{{.State.Status}}' "${VOICEVOX_CONTAINER_NAME}" 2>/dev/null || echo "unknown")

        local health
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${VOICEVOX_CONTAINER_NAME}" 2>/dev/null || echo "")

        if [ "${state}" = "running" ]; then
            if [ -n "${health}" ]; then
                case "${health}" in
                    healthy)
                        log "✅ VOICEVOX Nemo container is healthy"
                        return 0
                        ;;
                    unhealthy)
                        log "ERROR: VOICEVOX Nemo health check reported unhealthy"
                        docker logs "${VOICEVOX_CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
                        return 1
                        ;;
                esac
            fi

            if wget -q -O /dev/null "http://localhost:${VOICEVOX_PORT}${VOICEVOX_HEALTHCHECK_PATH}" >/dev/null 2>&1; then
                log "✅ VOICEVOX Nemo is responding on http://localhost:${VOICEVOX_PORT}${VOICEVOX_HEALTHCHECK_PATH}"
                return 0
            fi
        fi

        local elapsed=$(( $(date +%s) - start_ts ))
        if [ "${elapsed}" -ge "${VOICEVOX_START_TIMEOUT}" ]; then
            log "ERROR: VOICEVOX Nemo failed to become ready within ${VOICEVOX_START_TIMEOUT}s"
            docker logs "${VOICEVOX_CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
            return 1
        fi

        sleep 2
    done
}

# Dockerチェック
check_docker() {
    if ! command -v docker &> /dev/null; then
        log "ERROR: Docker is not installed"
        echo "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log "ERROR: Docker daemon is not running"
        echo "Please start Docker daemon:"
        echo "  sudo service docker start  # Linux"
        echo "  or open Docker Desktop     # Windows/Mac"
        exit 1
    fi
}

# ステータス確認
status() {
    local container_id
    container_id=$(docker ps -q --filter "name=^/${VOICEVOX_CONTAINER_NAME}$" 2>/dev/null)

    if [ -z "${container_id}" ]; then
        echo "❌ VOICEVOX Nemo is not running"
        return 1
    fi

    local state
    state=$(docker inspect --format='{{.State.Status}}' "${VOICEVOX_CONTAINER_NAME}" 2>/dev/null || echo "unknown")

    local health
    health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${VOICEVOX_CONTAINER_NAME}" 2>/dev/null || echo "N/A")

    local image
    image=$(docker inspect --format='{{.Config.Image}}' "${VOICEVOX_CONTAINER_NAME}" 2>/dev/null || echo "unknown")

    echo "✅ VOICEVOX Nemo is running"
    echo "   Container ID: ${container_id}"
    echo "   Image: ${image}"
    echo "   State: ${state}"
    echo "   Health: ${health}"
    echo "   Port: ${VOICEVOX_PORT}"

    if ! wget -q -O /dev/null "http://localhost:${VOICEVOX_PORT}${VOICEVOX_HEALTHCHECK_PATH}" >/dev/null 2>&1; then
        echo "   Endpoint: warming up..."
    fi

    return 0
}

# 起動
start() {
    log "Starting VOICEVOX Nemo server..."

    check_docker
    check_port_available

    # 既に起動中か確認
    if status &> /dev/null; then
        log "VOICEVOX Nemo is already running"
        return 0
    fi

    # 既存コンテナを削除（停止中の場合）
    docker rm -f "${VOICEVOX_CONTAINER_NAME}" 2>/dev/null || true

    # コンテナ起動
    log "Pulling Docker image (with retry if needed)..."
    if ! pull_image_with_retry; then
        echo "Failed to pull ${VOICEVOX_IMAGE}. See ${VOICEVOX_LOG} for details." >&2
        return 1
    fi

    log "Starting container ${VOICEVOX_CONTAINER_NAME} from ${VOICEVOX_IMAGE}..."

    local docker_args=(
        -d
        --name "${VOICEVOX_CONTAINER_NAME}"
        --restart "${VOICEVOX_RESTART_POLICY}"
        -p "${VOICEVOX_PORT}:50021"
                --health-cmd "wget -q -O /dev/null http://localhost:50021${VOICEVOX_HEALTHCHECK_PATH} || exit 1"         --health-interval "${VOICEVOX_HEALTH_INTERVAL}"
        --health-retries "${VOICEVOX_HEALTH_RETRIES}"
        --health-timeout "${VOICEVOX_HEALTH_TIMEOUT}"
        --health-start-period "${VOICEVOX_HEALTH_START_PERIOD}"
    )

    if [ -n "${VOICEVOX_CPU_LIMIT}" ]; then
        docker_args+=(--cpus "${VOICEVOX_CPU_LIMIT}")
    fi

    if [ -n "${VOICEVOX_MEMORY_LIMIT}" ]; then
        docker_args+=(--memory "${VOICEVOX_MEMORY_LIMIT}")
    fi

    docker_args+=("${VOICEVOX_IMAGE}")

    if ! docker run "${docker_args[@]}" >> "${VOICEVOX_LOG}" 2>&1; then
        log "ERROR: Failed to start VOICEVOX Nemo container"
        return 1
    fi

    log "Waiting for VOICEVOX Nemo to be ready..."
    if wait_for_health; then
        log "✅ VOICEVOX Nemo started successfully on port ${VOICEVOX_PORT}"
        status
        return 0
    fi

    log "ERROR: VOICEVOX Nemo did not pass health checks"
    docker logs "${VOICEVOX_CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
    docker stop --time "${VOICEVOX_STOP_TIMEOUT}" "${VOICEVOX_CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
    docker rm -f "${VOICEVOX_CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
    return 1
}

# 停止
stop() {
    log "Stopping VOICEVOX Nemo server..."

    if ! status &> /dev/null; then
        log "VOICEVOX Nemo is not running"
        return 0
    fi

    docker stop --time "${VOICEVOX_STOP_TIMEOUT}" "${VOICEVOX_CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
    log "✅ VOICEVOX Nemo stopped"
}

# 再起動
restart() {
    log "Restarting VOICEVOX Nemo server..."
    stop
    sleep 2
    start
}

# ログ表示
logs() {
    if [ -f "${VOICEVOX_LOG}" ]; then
        echo "=== VOICEVOX Nemo Manager Logs ==="
        tail -n 50 "${VOICEVOX_LOG}"
    fi

    echo ""
    echo "=== VOICEVOX Nemo Container Logs ==="
    docker logs "${VOICEVOX_CONTAINER_NAME}" 2>&1 || echo "Container not running"
}

# テスト
test() {
    log "Testing VOICEVOX Nemo synthesis (speaker ${VOICEVOX_SPEAKER})..."

    if ! status &> /dev/null; then
        log "ERROR: VOICEVOX Nemo is not running"
        echo "Please start it first: $0 start"
        return 1
    fi

    local test_text="こんにちは、音声合成のテストです。"
    local output_file="${LOG_DIR}/voicevox_test.wav"

    # URLエンコード
    local encoded_text=$(echo -n "$test_text" | python3 -c "import sys; from urllib.parse import quote; print(quote(sys.stdin.read()))")

    # クエリ作成
    log "Creating audio query..."
    local query=$(wget -qO- -S -X POST \
        "http://localhost:${VOICEVOX_PORT}/audio_query?text=${encoded_text}&speaker=${VOICEVOX_SPEAKER}")

    if [ -z "$query" ] || [ "$query" == "null" ]; then
        log "ERROR: Failed to create audio query"
        log "Response: $query"
        return 1
    fi

    # 音声合成
    log "Synthesizing audio..."
    wget -qO- -S -X POST \
        -H "Content-Type: application/json" \
        -d "$query" \
        "http://localhost:${VOICEVOX_PORT}/synthesis?speaker=${VOICEVOX_SPEAKER}" \
        -o "${output_file}"

    if [ -f "${output_file}" ] && [ -s "${output_file}" ]; then
        log "✅ Test successful! Audio saved to: ${output_file}"
        log "File size: $(du -h "${output_file}" | cut -f1)"
        return 0
    else
        log "ERROR: Test failed"
        return 1
    fi
}

# メイン処理
main() {
    case "${1:-}" in
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        logs)
            logs
            ;;
        test)
            test
            ;;
        *)
            echo "VOICEVOX Nemo Server Manager"
            echo ""
            echo "Usage: $0 {start|stop|restart|status|logs|test}"
            echo ""
            echo "Commands:"
            echo "  start   - Start VOICEVOX Nemo server"
            echo "  stop    - Stop VOICEVOX Nemo server"
            echo "  restart - Restart VOICEVOX Nemo server"
            echo "  status  - Check server status"
            echo "  logs    - Show logs"
            echo "  test    - Test audio synthesis"
            echo ""
            echo "Configuration:"
            echo "  Port: ${VOICEVOX_PORT}"
            echo "  Container: ${VOICEVOX_CONTAINER_NAME}"
            echo "  Image: ${VOICEVOX_IMAGE}"
            exit 1
            ;;
    esac
}

main "$@"
