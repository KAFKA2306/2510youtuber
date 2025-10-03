#!/bin/bash
# VOICEVOX Nemo サーバー管理スクリプト
# Usage: ./voicevox_manager.sh {start|stop|restart|status|logs}

set -euo pipefail

# 設定
VOICEVOX_PORT=50121
CONTAINER_NAME="voicevox-nemo"
DOCKER_IMAGE="voicevox/voicevox_engine:cpu-ubuntu20.04-latest"
LOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/logs"
VOICEVOX_LOG="${LOG_DIR}/voicevox_nemo.log"

# ディレクトリ作成
mkdir -p "${LOG_DIR}"

# ログ関数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${VOICEVOX_LOG}"
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
    local container_id=$(docker ps -q --filter "name=${CONTAINER_NAME}" 2>/dev/null)

    if [ -n "$container_id" ]; then
        echo "✅ VOICEVOX Nemo is running"
        echo "   Container ID: $container_id"
        echo "   Port: ${VOICEVOX_PORT}"

        # ヘルスチェック
        if curl -s "http://localhost:${VOICEVOX_PORT}/health" &> /dev/null; then
            echo "   Health: OK"
        else
            echo "   Health: Starting..."
        fi

        return 0
    else
        echo "❌ VOICEVOX Nemo is not running"
        return 1
    fi
}

# 起動
start() {
    log "Starting VOICEVOX Nemo server..."

    check_docker

    # 既に起動中か確認
    if status &> /dev/null; then
        log "VOICEVOX Nemo is already running"
        return 0
    fi

    # 既存コンテナを削除（停止中の場合）
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    # コンテナ起動
    log "Pulling Docker image (if needed)..."
    docker pull "${DOCKER_IMAGE}" >> "${VOICEVOX_LOG}" 2>&1

    log "Starting container..."
    docker run -d \
        --rm \
        --name "${CONTAINER_NAME}" \
        -p "${VOICEVOX_PORT}:50021" \
        "${DOCKER_IMAGE}" >> "${VOICEVOX_LOG}" 2>&1

    # 起動待機
    log "Waiting for VOICEVOX Nemo to be ready..."
    for i in {1..30}; do
        if curl -s "http://localhost:${VOICEVOX_PORT}/health" &> /dev/null; then
            log "✅ VOICEVOX Nemo started successfully on port ${VOICEVOX_PORT}"
            return 0
        fi
        sleep 2
        echo -n "."
    done

    log "ERROR: VOICEVOX Nemo failed to start within timeout"
    docker logs "${CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1
    return 1
}

# 停止
stop() {
    log "Stopping VOICEVOX Nemo server..."

    if ! status &> /dev/null; then
        log "VOICEVOX Nemo is not running"
        return 0
    fi

    docker stop "${CONTAINER_NAME}" >> "${VOICEVOX_LOG}" 2>&1 || true
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
    docker logs "${CONTAINER_NAME}" 2>&1 || echo "Container not running"
}

# テスト
test() {
    log "Testing VOICEVOX Nemo synthesis..."

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
    local query=$(curl -s -X POST \
        "http://localhost:${VOICEVOX_PORT}/audio_query?text=${encoded_text}&speaker=1")

    if [ -z "$query" ] || [ "$query" == "null" ]; then
        log "ERROR: Failed to create audio query"
        log "Response: $query"
        return 1
    fi

    # 音声合成
    log "Synthesizing audio..."
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$query" \
        "http://localhost:${VOICEVOX_PORT}/synthesis?speaker=1" \
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
            echo "  Container: ${CONTAINER_NAME}"
            echo "  Image: ${DOCKER_IMAGE}"
            exit 1
            ;;
    esac
}

main "$@"
