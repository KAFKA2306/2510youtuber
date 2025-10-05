"""Webインターフェース

Render上でのAPI提供とモニタリング用のWebアプリケーション
"""

import asyncio
import os
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request

from app.config import cfg
from app.integrations.discord import discord_notifier
from app.main import workflow
from app.integrations.sheets import sheets_manager

app = Flask(__name__)

# HTMLテンプレート
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTuber Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
        .status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .status.warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #0056b3; }
        .btn.danger { background: #dc3545; }
        .btn.danger:hover { background: #c82333; }
        .logs { background: #f8f9fa; padding: 15px; border-radius: 4px; font-family: monospace; max-height: 300px; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .loading { text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 YouTuber Dashboard</h1>

        <div class="card">
            <h2>System Status</h2>
            <div id="system-status">Loading...</div>
        </div>

        <div class="card">
            <h2>Quick Actions</h2>
            <button class="btn" onclick="runWorkflow('test')">🧪 Test Run</button>
            <button class="btn" onclick="runWorkflow('daily')">📅 Daily Run</button>
            <button class="btn" onclick="runWorkflow('special')">⭐ Special Run</button>
            <button class="btn danger" onclick="checkStatus()">🔄 Refresh Status</button>
        </div>

        <div class="card">
            <h2>Recent Runs</h2>
            <div id="recent-runs">Loading...</div>
        </div>

        <div class="card">
            <h2>System Logs</h2>
            <div id="system-logs" class="logs">Loading logs...</div>
        </div>
    </div>

    <script>
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                let html = '';
                for (const [service, status] of Object.entries(data.services)) {
                    const statusClass = status.status === 'ok' ? 'success' : 'error';
                    html += `<div class="status ${statusClass}">${service}: ${status.status}</div>`;
                }

                document.getElementById('system-status').innerHTML = html;
            } catch (error) {
                document.getElementById('system-status').innerHTML =
                    '<div class="status error">Failed to load status</div>';
            }
        }

        async function runWorkflow(mode) {
            if (!confirm(`Run ${mode} workflow? This may take several minutes.`)) return;

            try {
                const button = event.target;
                button.disabled = true;
                button.textContent = '⏳ Running...';

                const response = await fetch('/api/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: mode})
                });

                const result = await response.json();

                if (result.success) {
                    alert(`Workflow started successfully! Run ID: ${result.run_id}`);
                } else {
                    alert(`Failed to start workflow: ${result.error}`);
                }

                button.disabled = false;
                button.textContent = button.textContent.replace('⏳ Running...', '');
                loadRecentRuns();

            } catch (error) {
                alert(`Error: ${error.message}`);
                button.disabled = false;
            }
        }

        async function loadRecentRuns() {
            try {
                const response = await fetch('/api/runs');
                const runs = await response.json();

                let html = '<table><tr><th>Run ID</th><th>Mode</th><th>Status</th><th>Started</th><th>Video URL</th></tr>';

                for (const run of runs.slice(0, 10)) {
                    const videoLink = run.video_url ?
                        `<a href="${run.video_url}" target="_blank">View</a>` :
                        'N/A';

                    html += `<tr>
                        <td>${run.run_id}</td>
                        <td>${run.mode || 'unknown'}</td>
                        <td>${run.status}</td>
                        <td>${new Date(run.started_at).toLocaleString()}</td>
                        <td>${videoLink}</td>
                    </tr>`;
                }

                html += '</table>';
                document.getElementById('recent-runs').innerHTML = html;

            } catch (error) {
                document.getElementById('recent-runs').innerHTML =
                    '<div class="status error">Failed to load runs</div>';
            }
        }

        async function loadLogs() {
            try {
                const response = await fetch('/api/logs');
                const logs = await response.text();
                document.getElementById('system-logs').textContent = logs;
            } catch (error) {
                document.getElementById('system-logs').textContent = 'Failed to load logs';
            }
        }

        // 初期化
        checkStatus();
        loadRecentRuns();
        loadLogs();

        // 定期更新
        setInterval(() => {
            checkStatus();
            loadRecentRuns();
        }, 30000); // 30秒ごと
    </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    """ダッシュボード表示"""
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/status")
def api_status():
    """システム状態API"""
    status = {"timestamp": datetime.now().isoformat(), "services": {}}

    # 各サービスの状態チェック
    try:
        # Anthropic API
        if cfg.anthropic_api_key:
            status["services"]["Anthropic"] = {"status": "ok", "message": "API key configured"}
        else:
            status["services"]["Anthropic"] = {"status": "error", "message": "API key missing"}

        # Gemini API
        if cfg.gemini_api_keys:
            status["services"]["Gemini"] = {"status": "ok", "message": f"{len(cfg.gemini_api_keys)} keys configured"}
        else:
            status["services"]["Gemini"] = {"status": "error", "message": "API keys missing"}

        # ElevenLabs API
        if cfg.elevenlabs_api_key:
            status["services"]["ElevenLabs"] = {"status": "ok", "message": "API key configured"}
        else:
            status["services"]["ElevenLabs"] = {"status": "error", "message": "API key missing"}

        # Google Services
        if cfg.google_application_credentials:
            status["services"]["Google"] = {"status": "ok", "message": "Credentials configured"}
        else:
            status["services"]["Google"] = {"status": "error", "message": "Credentials missing"}

        # Discord
        if cfg.discord_webhook_url:
            status["services"]["Discord"] = {"status": "ok", "message": "Webhook configured"}
        else:
            status["services"]["Discord"] = {"status": "warning", "message": "Webhook not configured"}

    except Exception as e:
        status["services"]["System"] = {"status": "error", "message": str(e)}

    return jsonify(status)


@app.route("/api/run", methods=["POST"])
def api_run():
    """ワークフロー実行API"""
    try:
        data = request.get_json()
        mode = data.get("mode", "test")

        if mode not in ["daily", "special", "test"]:
            return jsonify({"success": False, "error": "Invalid mode"}), 400

        # 非同期でワークフローを実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def run_workflow():
            return loop.run_until_complete(workflow.execute_full_workflow(mode))

        # バックグラウンドで実行
        import threading

        thread = threading.Thread(target=run_workflow)
        thread.start()

        return jsonify(
            {"success": True, "message": f"Workflow started in {mode} mode", "run_id": workflow.run_id or "unknown"}
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/runs")
def api_runs():
    """実行履歴API"""
    try:
        if sheets_manager:
            runs = sheets_manager.get_recent_runs(limit=20)
            return jsonify(runs)
        else:
            return jsonify([])

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs")
def api_logs():
    """ログAPI"""
    try:
        log_file = "logs/log"
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 最新100行を返す
                return "\n".join(lines[-100:])
        else:
            return "No log file found"

    except Exception as e:
        return f"Error reading logs: {e}"


@app.route("/api/health")
def health_check():
    """ヘルスチェック"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "1.0.0"})


@app.route("/api/webhook/discord", methods=["POST"])
def discord_webhook():
    """Discord Webhook エンドポイント"""
    try:
        data = request.get_json()
        message = data.get("message", "Test message")
        level = data.get("level", "info")

        discord_notifier.notify(message, level=level)

        return jsonify({"success": True, "message": "Notification sent"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # 開発用サーバー
    port = int(os.environ.get("PORT", 5000))
    debug = cfg.debug

    app.run(host="0.0.0.0", port=port, debug=debug)
