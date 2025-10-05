import { get, writable } from 'svelte/store';
import { connectJobStream, createJob, getJob, getJobLogs, listCommands } from '$lib/apiClient';
import type { CommandDefinition, JobStatus, JobSummary, LogEvent } from '$lib/types';

const commands = writable<CommandDefinition[]>([]);
const commandsLoading = writable(false);
const commandsError = writable<string | null>(null);

const jobs = writable<JobSummary[]>([]);
const jobLogs = writable<Record<string, LogEvent[]>>({});
const selectedJobId = writable<string | null>(null);
const launchingJob = writable(false);
const jobError = writable<string | null>(null);

const fallbackCommands: CommandDefinition[] = [
    {
        id: 'daily_workflow',
        label: 'デイリー自動生成',
        description: 'uv run python3 -m app.main daily',
        runner: 'python',
        params_schema: {
            type: 'object',
            properties: {
                mode: {
                    type: 'string',
                    enum: ['daily', 'backfill'],
                    description: '実行モード (daily/backfill)',
                    default: 'daily'
                }
            },
            required: ['mode']
        }
    },
    {
        id: 'verify_config',
        label: '設定チェック',
        description: 'uv run python -m app.verify',
        runner: 'cli',
        params_schema: {
            type: 'object',
            properties: {}
        }
    },
    {
        id: 'generate_analytics',
        label: '分析レポート',
        description: 'python scripts/tasks.py analytics',
        runner: 'cli',
        params_schema: {
            type: 'object',
            properties: {
                include_trends: {
                    type: 'string',
                    enum: ['enabled', 'disabled'],
                    description: 'トレンド分析を含めるか',
                    default: 'enabled'
                }
            }
        }
    }
];

const logStreams = new Map<string, WebSocket>();
const mockJobTimers = new Map<string, () => void>();
const mockLogIntervals = new Map<string, () => void>();

export async function loadCommands(): Promise<void> {
    commandsLoading.set(true);
    commandsError.set(null);
    try {
        const remote = await listCommands();
        if (!remote || remote.length === 0) {
            commands.set(fallbackCommands);
            commandsError.set('APIからコマンド一覧を取得できませんでした。サンプル定義を表示しています。');
        } else {
            commands.set(remote);
        }
    } catch (error) {
        console.warn('Failed to load commands, falling back to static definitions.', error);
        commands.set(fallbackCommands);
        commandsError.set('APIに接続できないため、サンプルのコマンド一覧を表示しています。');
    } finally {
        commandsLoading.set(false);
    }
}

export async function launchJob(commandId: string, params: Record<string, unknown>): Promise<void> {
    launchingJob.set(true);
    jobError.set(null);
    try {
        const job = await createJob({ command_id: commandId, params });
        registerOrUpdateJob(job);
        await fetchLogs(job.id);
        attachLogStream(job.id);
    } catch (error) {
        console.warn('Failed to launch job via API, falling back to mock execution.', error);
        jobError.set('APIに接続できないため、モックジョブを開始しました。');
        const job = createMockJob(commandId, params);
        registerOrUpdateJob(job);
        startMockLifecycle(job);
    } finally {
        launchingJob.set(false);
    }
}

export async function refreshJob(jobId: string): Promise<void> {
    try {
        const job = await getJob(jobId);
        registerOrUpdateJob(job);
        await fetchLogs(jobId);
    } catch (error) {
        console.warn('Failed to refresh job from API.', error);
    }
}

export async function selectJob(jobId: string | null): Promise<void> {
    selectedJobId.set(jobId);
    if (!jobId) {
        return;
    }

    await fetchLogs(jobId);
    const job = get(jobs).find((item) => item.id === jobId);
    if (job && (job.status === 'pending' || job.status === 'running')) {
        attachLogStream(jobId);
    }
}

export function clearJobMessage(): void {
    jobError.set(null);
}

export const jobStores = {
    commands,
    commandsLoading,
    commandsError,
    jobs,
    jobLogs,
    selectedJobId,
    launchingJob,
    jobError
};

function registerOrUpdateJob(job: JobSummary): void {
    jobs.update((current) => {
        const existingIndex = current.findIndex((item) => item.id === job.id);
        const updated = existingIndex >= 0 ? [...current] : [job, ...current];
        if (existingIndex >= 0) {
            updated[existingIndex] = { ...updated[existingIndex], ...job };
        } else {
            selectedJobId.set(job.id);
        }
        return updated.sort((a, b) => {
            const aTs = new Date(a.created_at ?? a.started_at ?? 0).getTime();
            const bTs = new Date(b.created_at ?? b.started_at ?? 0).getTime();
            return bTs - aTs;
        });
    });
}

async function fetchLogs(jobId: string): Promise<void> {
    try {
        const logs = await getJobLogs(jobId, 400);
        setLogs(jobId, logs);
    } catch (error) {
        if (!mockJobTimers.has(jobId) && !mockLogIntervals.has(jobId)) {
            console.debug('Failed to fetch logs for job', jobId, error);
        }
    }
}

function setLogs(jobId: string, logs: LogEvent[]): void {
    jobLogs.update((current) => ({
        ...current,
        [jobId]: logs.slice(-400)
    }));
}

function appendLog(jobId: string, events: LogEvent | LogEvent[]): void {
    const newEvents = Array.isArray(events) ? events : [events];
    jobLogs.update((current) => {
        const existing = current[jobId] ?? [];
        const merged = [...existing, ...newEvents];
        return {
            ...current,
            [jobId]: merged.slice(-400)
        };
    });
}

function attachLogStream(jobId: string): void {
    if (logStreams.has(jobId)) {
        return;
    }

    try {
        const socket = connectJobStream(jobId);
        socket.addEventListener('message', (event) => {
            try {
                const data = JSON.parse(event.data) as LogEvent;
                appendLog(jobId, { ...data, job_id: jobId });
            } catch (parseError) {
                console.warn('Failed to parse log event', parseError);
            }
        });
        socket.addEventListener('close', () => {
            logStreams.delete(jobId);
        });
        socket.addEventListener('error', (event) => {
            console.warn('Log stream error', event);
            logStreams.delete(jobId);
            startMockLogStream(jobId);
        });
        logStreams.set(jobId, socket);
    } catch (error) {
        console.warn('Failed to open WebSocket log stream, using mock stream instead.', error);
        startMockLogStream(jobId);
    }
}

function closeLogStream(jobId: string): void {
    const socket = logStreams.get(jobId);
    if (socket) {
        socket.close();
        logStreams.delete(jobId);
    }
    closeMockLogInterval(jobId);
}

function startMockLogStream(jobId: string): void {
    if (mockLogIntervals.has(jobId)) {
        return;
    }
    const stop = createMockLogTicker(jobId);
    mockLogIntervals.set(jobId, stop);
}

function createMockJob(commandId: string, params: Record<string, unknown>): JobSummary {
    const now = new Date().toISOString();
    return {
        id: `mock-${Math.random().toString(36).slice(2, 10)}`,
        command_id: commandId,
        status: 'running',
        params,
        created_at: now,
        started_at: now,
        artifacts: []
    };
}

function startMockLifecycle(job: JobSummary): void {
    const jobId = job.id;
    const startTs = Date.now();
    const willFail = Math.random() < 0.12;

    const timers: number[] = [];
    const clearTimers = () => {
        timers.forEach((timer) => window.clearTimeout(timer));
        mockJobTimers.delete(jobId);
    };

    mockJobTimers.set(jobId, clearTimers);

    appendLog(jobId, {
        job_id: jobId,
        level: 'info',
        ts: new Date(startTs).toISOString(),
        line: `${job.command_id} を開始しました。`
    });

    timers.push(
        window.setTimeout(() => {
            appendLog(jobId, {
                job_id: jobId,
                level: 'info',
                ts: new Date().toISOString(),
                line: '依存関係とリソースを初期化しています...'
            });
        }, 600)
    );

    timers.push(
        window.setTimeout(() => {
            appendLog(jobId, {
                job_id: jobId,
                level: 'info',
                ts: new Date().toISOString(),
                line: 'CrewAIフローを実行中...'
            });
        }, 1400)
    );

    timers.push(
        window.setTimeout(() => {
            appendLog(jobId, {
                job_id: jobId,
                level: willFail ? 'error' : 'info',
                ts: new Date().toISOString(),
                line: willFail
                    ? '品質チェックでエラーが発生しました。ワークフローを中断します。'
                    : '動画生成が完了しました。メタデータを整形しています...'
            });
        }, 2600)
    );

    timers.push(
        window.setTimeout(() => {
            const status: JobStatus = willFail ? 'failed' : 'succeeded';
            updateJob(jobId, {
                status,
                finished_at: new Date().toISOString(),
                message: willFail ? '品質検証でエラーが発生しました。' : 'ジョブが正常に完了しました。'
            });
            appendLog(jobId, {
                job_id: jobId,
                level: willFail ? 'error' : 'info',
                ts: new Date().toISOString(),
                line: willFail ? 'ジョブは失敗として終了しました。' : '成果物がアーカイブに保存されました。'
            });
            if (!willFail) {
                appendLog(jobId, {
                    job_id: jobId,
                    level: 'info',
                    ts: new Date().toISOString(),
                    line: 'YouTubeメタデータを出力しました。'
                });
            }
            closeLogStream(jobId);
            clearTimers();
        }, 4200)
    );
}

function updateJob(jobId: string, patch: Partial<JobSummary>): void {
    jobs.update((current) =>
        current.map((item) => (item.id === jobId ? { ...item, ...patch } : item))
    );
}

function createMockLogTicker(jobId: string): () => void {
    let counter = 0;
    const interval = window.setInterval(() => {
        counter += 1;
        appendLog(jobId, {
            job_id: jobId,
            level: 'info',
            ts: new Date().toISOString(),
            line: `ログストリームを監視中... (${counter})`
        });
    }, 1500);

    return () => {
        window.clearInterval(interval);
        mockLogIntervals.delete(jobId);
    };
}

function closeMockLogInterval(jobId: string): void {
    const stop = mockLogIntervals.get(jobId);
    if (stop) {
        stop();
        mockLogIntervals.delete(jobId);
    }
}
