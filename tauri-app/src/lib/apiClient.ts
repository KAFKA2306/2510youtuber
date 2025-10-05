import type { CommandDefinition, JobSummary, LogEvent } from './types';

const DEFAULT_BASE_URL = 'http://localhost:8000';

function resolveBaseUrl(): string {
    const configured = import.meta.env.VITE_GUI_API_BASE as string | undefined;
    return configured?.replace(/\/$/, '') || DEFAULT_BASE_URL;
}

function buildUrl(path: string): string {
    const base = resolveBaseUrl();
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${base}${normalizedPath}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(buildUrl(path), {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(init?.headers ?? {})
        }
    });

    if (!response.ok) {
        const detail = await response.text().catch(() => '');
        throw new Error(`API request failed with status ${response.status}: ${detail}`);
    }

    return (await response.json()) as T;
}

export async function listCommands(): Promise<CommandDefinition[]> {
    return fetchJson<CommandDefinition[]>('/commands');
}

export async function createJob(payload: {
    command_id: string;
    params?: Record<string, unknown>;
}): Promise<JobSummary> {
    return fetchJson<JobSummary>('/jobs', {
        method: 'POST',
        body: JSON.stringify(payload)
    });
}

export async function getJob(jobId: string): Promise<JobSummary> {
    return fetchJson<JobSummary>(`/jobs/${jobId}`);
}

export async function getJobLogs(jobId: string, tail = 200): Promise<LogEvent[]> {
    const params = new URLSearchParams({ tail: tail.toString() });
    return fetchJson<LogEvent[]>(`/jobs/${jobId}/logs?${params.toString()}`);
}

export function connectJobStream(jobId: string): WebSocket {
    const url = new URL(buildUrl(`/jobs/${jobId}/stream`));
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return new WebSocket(url);
}

export type ApiClient = {
    listCommands: typeof listCommands;
    createJob: typeof createJob;
    getJob: typeof getJob;
    getJobLogs: typeof getJobLogs;
    connectJobStream: typeof connectJobStream;
};
