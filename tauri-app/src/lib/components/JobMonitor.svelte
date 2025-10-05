<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import type { CommandDefinition, JobSummary, LogEvent } from '$lib/types';

    export let jobs: JobSummary[] = [];
    export let selectedJobId: string | null = null;
    export let logs: LogEvent[] = [];
    export let commands: Record<string, CommandDefinition> = {};

    const dispatch = createEventDispatcher<{ select: { jobId: string } }>();

    $: selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;

    function formatDate(value?: string | null): string {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return new Intl.DateTimeFormat('ja-JP', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }).format(date);
    }

    function formatStatus(status: JobSummary['status']): string {
        switch (status) {
            case 'pending':
                return '待機中';
            case 'running':
                return '実行中';
            case 'succeeded':
                return '完了';
            case 'failed':
                return '失敗';
            case 'cancelled':
                return 'キャンセル';
            default:
                return status;
        }
    }

    function statusTone(status: JobSummary['status']): string {
        if (status === 'succeeded') return 'success';
        if (status === 'failed') return 'danger';
        if (status === 'running') return 'running';
        return 'neutral';
    }

    function handleSelect(jobId: string): void {
        dispatch('select', { jobId });
    }
</script>

<section class="monitor">
    <header class="monitor__header">
        <div>
            <h2>実行モニタ</h2>
            <p class="monitor__subtitle">進行中/完了済みのジョブを追跡し、ログをリアルタイムに確認できます。</p>
        </div>
    </header>

    <div class="monitor__body">
        <aside class="monitor__jobs">
            <h3>ジョブ履歴</h3>
            {#if jobs.length === 0}
                <p class="monitor__empty">まだジョブがありません。左側からジョブを開始してください。</p>
            {:else}
                <ul>
                    {#each jobs as job}
                        <li class:selected={job.id === selectedJobId}>
                            <button type="button" on:click={() => handleSelect(job.id)}>
                                <div class={`status-badge status-badge--${statusTone(job.status)}`}>
                                    {formatStatus(job.status)}
                                </div>
                                <div class="job-meta">
                                    <span class="job-command">{commands[job.command_id]?.label ?? job.command_id}</span>
                                    <span class="job-time">開始 {formatDate(job.started_at ?? job.created_at)}</span>
                                </div>
                            </button>
                        </li>
                    {/each}
                </ul>
            {/if}
        </aside>

        <article class="monitor__details">
            {#if selectedJob}
                <header class="details__header">
                    <div>
                        <h3>{commands[selectedJob.command_id]?.label ?? selectedJob.command_id}</h3>
                        <p class="details__status">{formatStatus(selectedJob.status)}</p>
                    </div>
                    <div class={`status-pill status-pill--${statusTone(selectedJob.status)}`}>
                        {formatStatus(selectedJob.status)}
                    </div>
                </header>

                <dl class="details__grid">
                    <div>
                        <dt>ジョブID</dt>
                        <dd>{selectedJob.id}</dd>
                    </div>
                    <div>
                        <dt>開始</dt>
                        <dd>{formatDate(selectedJob.started_at ?? selectedJob.created_at)}</dd>
                    </div>
                    <div>
                        <dt>終了</dt>
                        <dd>{formatDate(selectedJob.finished_at)}</dd>
                    </div>
                    <div>
                        <dt>ステータス</dt>
                        <dd>{formatStatus(selectedJob.status)}</dd>
                    </div>
                    <div class="details__full">
                        <dt>パラメータ</dt>
                        <dd>
                            <pre>{JSON.stringify(selectedJob.params ?? {}, null, 2)}</pre>
                        </dd>
                    </div>
                    {#if selectedJob.message}
                        <div class="details__full">
                            <dt>メッセージ</dt>
                            <dd>{selectedJob.message}</dd>
                        </div>
                    {/if}
                </dl>

                <section class="log-viewer">
                    <header>
                        <h4>ライブログ</h4>
                        <span>{logs.length}件</span>
                    </header>
                    <div class="log-viewer__scroller">
                        {#if logs.length === 0}
                            <p class="monitor__empty">ログはまだありません。ジョブの開始を待機しています。</p>
                        {:else}
                            <ul>
                                {#each logs as log (log.ts + log.line + log.level)}
                                    <li class={`log log--${log.level}`}>
                                        <span class="log__ts">{formatDate(log.ts)}</span>
                                        <span class="log__level">{log.level.toUpperCase()}</span>
                                        <span class="log__line">{log.line}</span>
                                    </li>
                                {/each}
                            </ul>
                        {/if}
                    </div>
                </section>
            {:else}
                <div class="monitor__placeholder">
                    <p>ジョブを選択すると詳細とログが表示されます。</p>
                </div>
            {/if}
        </article>
    </div>
</section>

<style>
    .monitor {
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
        padding: 1.5rem;
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.75);
        color: #e2e8f0;
        border: 1px solid rgba(148, 163, 184, 0.2);
        min-height: 100%;
    }

    .monitor__header h2 {
        margin: 0;
        font-size: 1.4rem;
    }

    .monitor__subtitle {
        margin: 0.2rem 0 0;
        color: rgba(226, 232, 240, 0.7);
        font-size: 0.9rem;
    }

    .monitor__body {
        display: grid;
        grid-template-columns: 240px 1fr;
        gap: 1.25rem;
        min-height: 24rem;
    }

    .monitor__jobs {
        background: rgba(15, 23, 42, 0.55);
        border-radius: 14px;
        padding: 1rem;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }

    .monitor__jobs h3 {
        margin: 0 0 0.75rem;
        font-size: 1.05rem;
    }

    .monitor__jobs ul {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .monitor__jobs li {
        border-radius: 12px;
        padding: 0.75rem;
        background: rgba(30, 41, 59, 0.7);
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        border: 1px solid transparent;
        cursor: default;
        transition: border-color 0.2s ease, transform 0.2s ease;
    }

    .monitor__jobs li.selected {
        border-color: rgba(56, 189, 248, 0.6);
        transform: translateY(-2px);
    }

    .monitor__jobs li:hover {
        border-color: rgba(148, 163, 184, 0.6);
    }

    .monitor__jobs li button {
        all: unset;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        width: 100%;
        text-align: left;
        cursor: pointer;
    }

    .monitor__jobs li button:focus-visible {
        outline: 2px solid rgba(56, 189, 248, 0.6);
        outline-offset: 2px;
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.15rem 0.6rem;
        border-radius: 9999px;
        width: fit-content;
    }

    .status-badge--running {
        background: rgba(56, 189, 248, 0.2);
        color: #38bdf8;
    }

    .status-badge--success {
        background: rgba(74, 222, 128, 0.2);
        color: #4ade80;
    }

    .status-badge--danger {
        background: rgba(248, 113, 113, 0.2);
        color: #f87171;
    }

    .status-badge--neutral {
        background: rgba(148, 163, 184, 0.2);
        color: #cbd5f5;
    }

    .job-meta {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
    }

    .job-command {
        font-weight: 600;
    }

    .job-time {
        font-size: 0.8rem;
        color: rgba(148, 163, 184, 0.9);
    }

    .monitor__details {
        background: rgba(15, 23, 42, 0.55);
        border-radius: 14px;
        padding: 1.25rem;
        border: 1px solid rgba(148, 163, 184, 0.2);
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .details__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .details__header h3 {
        margin: 0;
        font-size: 1.3rem;
    }

    .details__status {
        margin: 0.2rem 0 0;
        color: rgba(226, 232, 240, 0.7);
        font-size: 0.9rem;
    }

    .status-pill {
        padding: 0.4rem 0.8rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid transparent;
    }

    .status-pill--running {
        background: rgba(56, 189, 248, 0.15);
        border-color: rgba(56, 189, 248, 0.3);
        color: #38bdf8;
    }

    .status-pill--success {
        background: rgba(74, 222, 128, 0.15);
        border-color: rgba(74, 222, 128, 0.3);
        color: #4ade80;
    }

    .status-pill--danger {
        background: rgba(248, 113, 113, 0.15);
        border-color: rgba(248, 113, 113, 0.35);
        color: #f87171;
    }

    .details__grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
    }

    .details__grid div {
        background: rgba(30, 41, 59, 0.65);
        border-radius: 12px;
        padding: 0.8rem;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }

    .details__grid dt {
        font-size: 0.75rem;
        text-transform: uppercase;
        color: rgba(148, 163, 184, 0.8);
        margin: 0 0 0.35rem;
        letter-spacing: 0.05em;
    }

    .details__grid dd {
        margin: 0;
        font-size: 0.95rem;
        word-break: break-all;
    }

    .details__full {
        grid-column: 1 / -1;
    }

    .details__full pre {
        margin: 0;
        background: rgba(15, 23, 42, 0.8);
        border-radius: 10px;
        padding: 0.75rem;
        overflow-x: auto;
        font-size: 0.85rem;
        line-height: 1.4;
    }

    .log-viewer {
        background: rgba(30, 41, 59, 0.65);
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.2);
        display: flex;
        flex-direction: column;
        max-height: 18rem;
    }

    .log-viewer header {
        display: flex;
        justify-content: space-between;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    }

    .log-viewer__scroller {
        overflow-y: auto;
        padding: 0.75rem 1rem;
    }

    .log-viewer ul {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .log {
        display: grid;
        grid-template-columns: 90px 80px 1fr;
        gap: 0.5rem;
        font-size: 0.85rem;
        padding: 0.4rem 0.6rem;
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid transparent;
    }

    .log--info {
        border-color: rgba(59, 130, 246, 0.25);
    }

    .log--warning {
        border-color: rgba(251, 191, 36, 0.35);
    }

    .log--error,
    .log--critical {
        border-color: rgba(248, 113, 113, 0.4);
    }

    .log__ts {
        color: rgba(148, 163, 184, 0.9);
    }

    .log__level {
        font-weight: 600;
        letter-spacing: 0.05em;
    }

    .log__line {
        white-space: pre-wrap;
    }

    .monitor__empty {
        margin: 0;
        color: rgba(148, 163, 184, 0.8);
        font-size: 0.9rem;
    }

    .monitor__placeholder {
        flex: 1;
        display: grid;
        place-items: center;
        color: rgba(148, 163, 184, 0.75);
        border: 2px dashed rgba(148, 163, 184, 0.25);
        border-radius: 12px;
    }

    @media (max-width: 960px) {
        .monitor__body {
            grid-template-columns: 1fr;
        }

        .monitor__jobs {
            order: 2;
        }

        .monitor__details {
            order: 1;
        }
    }
</style>
