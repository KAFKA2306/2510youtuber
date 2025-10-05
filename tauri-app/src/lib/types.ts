export type CommandParameterSchema = {
    type: string;
    title?: string;
    description?: string;
    enum?: string[];
    default?: unknown;
    properties?: Record<string, CommandParameterSchema & { required?: boolean }>;
    items?: CommandParameterSchema;
    required?: string[];
};

export interface CommandDefinition {
    id: string;
    label: string;
    description?: string;
    runner?: string;
    params_schema?: CommandParameterSchema;
}

export type JobStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface JobArtifact {
    name: string;
    path: string;
    type?: string;
}

export interface JobSummary {
    id: string;
    command_id: string;
    status: JobStatus;
    params?: Record<string, unknown>;
    created_at?: string;
    started_at?: string | null;
    finished_at?: string | null;
    artifacts?: JobArtifact[];
    message?: string;
}

export type LogLevel = 'debug' | 'info' | 'warning' | 'error' | 'critical';

export interface LogEvent {
    job_id: string;
    line: string;
    level: LogLevel;
    ts?: string;
    source?: string;
}
