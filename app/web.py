"""Web dashboard and API endpoints for monitoring automated YouTube runs."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List
from flask import Flask, jsonify, render_template_string, request
from .config import cfg
from .discord import discord_notifier
from .sheets import sheets_manager
from .workflow_runner import WorkflowRunner
app = Flask(__name__)
_runner = WorkflowRunner()
_ALLOWED_MODES = {"daily", "special", "test"}
_LOG_PATH = Path("logs/log")
@dataclass(frozen=True)
class ServiceStatus:
    name: str
    status: str
    message: str
    def as_dict(self) -> Dict[str, str]:
        return {"status": self.status, "message": self.message}
def _service_statuses() -> Dict[str, Dict[str, str]]:
    statuses: List[ServiceStatus] = []
    try:
        statuses.append(
            ServiceStatus(
                "Anthropic",
                "ok" if cfg.anthropic_api_key else "error",
                "API key configured" if cfg.anthropic_api_key else "API key missing",
            )
        )
        statuses.append(
            ServiceStatus(
                "Gemini",
                "ok" if cfg.gemini_api_keys else "error",
                f"{len(cfg.gemini_api_keys)} keys configured" if cfg.gemini_api_keys else "API keys missing",
            )
        )
        statuses.append(
            ServiceStatus(
                "ElevenLabs",
                "ok" if cfg.elevenlabs_api_key else "error",
                "API key configured" if cfg.elevenlabs_api_key else "API key missing",
            )
        )
        statuses.append(
            ServiceStatus(
                "Google",
                "ok" if cfg.google_application_credentials else "error",
                "Credentials configured" if cfg.google_application_credentials else "Credentials missing",
            )
        )
        statuses.append(
            ServiceStatus(
                "Discord",
                "ok" if cfg.discord_webhook_url else "warning",
                "Webhook configured" if cfg.discord_webhook_url else "Webhook not configured",
            )
        )
    except Exception as error:
        statuses.append(ServiceStatus("System", "error", str(error)))
    return {status.name: status.as_dict() for status in statuses}
def _merge_run_history(active: Iterable[Dict[str, str]], archived: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    history: Dict[str, Dict[str, str]] = {}
    for run in archived:
        run_id = run.get("run_id")
        if run_id:
            history[run_id] = run
    for run in active:
        run_id = run.get("run_id")
        if not run_id:
            continue
        merged = history.get(run_id, {}).copy()
        merged.update({k: v for k, v in run.items() if v is not None})
        history[run_id] = merged
    return sorted(history.values(), key=lambda item: item.get("started_at", ""), reverse=True)
def _tail_logs(limit: int = 100) -> str:
    if not _LOG_PATH.exists():
        return "No log file found"
    with _LOG_PATH.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    return "\n".join(lines[-limit:])
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTuber Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background:
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
        .status.success { background:
        .status.error { background:
        .status.warning { background:
        .btn { background:
        .btn:hover { background:
        .btn.danger { background:
        .btn.danger:hover { background:
        .logs { background:
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid
        th { background-color:
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
            <button class="btn" onclick="runWorkflow(event, 'test')">🧪 Test Run</button>
            <button class="btn" onclick="runWorkflow(event, 'daily')">📅 Daily Run</button>
            <button class="btn" onclick="runWorkflow(event, 'special')">⭐ Special Run</button>
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
        function renderStatus(status) {
            let html = '';
            for (const [service, info] of Object.entries(status.services)) {
                const statusClass = info.status === 'ok' ? 'success' : (info.status === 'warning' ? 'warning' : 'error');
                html += `<div class="status ${statusClass}">${service}: ${info.message}</div>`;
            }
            document.getElementById('system-status').innerHTML = html;
        }
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                renderStatus(data);
            } catch (error) {
                document.getElementById('system-status').innerHTML = '<div class="status error">Failed to load status</div>';
            }
        }
        async function runWorkflow(event, mode) {
            if (!confirm(`Run ${mode} workflow? This may take several minutes.`)) return;
            const button = event.target;
            try {
                button.disabled = true;
                const originalLabel = button.textContent;
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
                button.textContent = originalLabel;
                button.disabled = false;
                loadRecentRuns();
            } catch (error) {
                alert(`Error: ${error.message}`);
                button.disabled = false;
            }
        }
        function renderRuns(runs) {
            if (!runs.length) {
                document.getElementById('recent-runs').innerHTML = '<div class="status warning">No run history available</div>';
                return;
            }
            let html = '<table><tr><th>Run ID</th><th>Mode</th><th>Status</th><th>Started</th><th>Finished</th><th>Video URL</th></tr>';
            for (const run of runs.slice(0, 10)) {
                const started = run.started_at ? new Date(run.started_at).toLocaleString() : 'N/A';
                const finished = run.finished_at ? new Date(run.finished_at).toLocaleString() : 'In progress';
                const videoLink = run.video_url ? `<a href="${run.video_url}" target="_blank">View</a>` : 'N/A';
                html += `<tr>
                    <td>${run.run_id || 'pending'}</td>
                    <td>${run.mode || 'unknown'}</td>
                    <td>${run.status}</td>
                    <td>${started}</td>
                    <td>${finished}</td>
                    <td>${videoLink}</td>
                </tr>`;
            }
            html += '</table>';
            document.getElementById('recent-runs').innerHTML = html;
        }
        async function loadRecentRuns() {
            try {
                const response = await fetch('/api/runs');
                const runs = await response.json();
                renderRuns(runs);
            } catch (error) {
                document.getElementById('recent-runs').innerHTML = '<div class="status error">Failed to load runs</div>';
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
        checkStatus();
        loadRecentRuns();
        loadLogs();
        setInterval(() => {
            checkStatus();
            loadRecentRuns();
        }, 30000);
    </script>
</body>
</html>
"""
@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)
@app.route("/api/status")
def api_status():
    return jsonify({"timestamp": datetime.utcnow().isoformat(), "services": _service_statuses()})
@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "test")
    if mode not in _ALLOWED_MODES:
        return jsonify({"success": False, "error": "Invalid mode"}), 400
    execution = _runner.start(mode)
    run_id = execution.wait_until_started(timeout=5)
    if not run_id:
        execution.wait_until_finished(timeout=0)
        return jsonify({"success": False, "error": execution.error or "Failed to allocate run"}), 500
    return jsonify({"success": True, "message": f"Workflow started in {mode} mode", "run_id": run_id})
@app.route("/api/runs")
def api_runs():
    active_runs = [execution.to_dict() for execution in _runner.list_recent(limit=20)]
    sheet_runs: Iterable[Dict[str, str]] = []
    if sheets_manager:
        try:
            sheet_runs = sheets_manager.get_recent_runs(limit=20)
        except Exception as error:
            discord_notifier.notify_blocking(f"Sheets run history error: {error}", level="error")
    return jsonify(_merge_run_history(active_runs, sheet_runs))
@app.route("/api/logs")
def api_logs():
    try:
        return _tail_logs()
    except Exception as error:
        return f"Error reading logs: {error}"
@app.route("/api/health")
def health_check():
    return jsonify({"status": "healthy"})
@app.route("/api/webhook/discord", methods=["POST"])
def discord_webhook():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "Test message")
    level = data.get("level", "info")
    try:
        discord_notifier.notify_blocking(message, level=level)
        return jsonify({"success": True, "message": "Notification sent"})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500
@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found"}), 404
@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"error": "Internal server error"}), 500
if __name__ == "__main__":
    port = int(getattr(cfg, "port", 5000))
    app.run(host="0.0.0.0", port=port, debug=bool(getattr(cfg, "debug", False)))
