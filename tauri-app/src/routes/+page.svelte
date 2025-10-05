<script lang="ts">
    import { onMount } from 'svelte';
    import JobLauncher from '$lib/components/JobLauncher.svelte';
    import JobMonitor from '$lib/components/JobMonitor.svelte';
    import type { CommandDefinition } from '$lib/types';
    import { jobStores, launchJob, loadCommands, selectJob, clearJobMessage } from '$lib/stores/jobStore';

    const { commands, commandsLoading, commandsError, jobs, jobLogs, selectedJobId, launchingJob, jobError } = jobStores;

    onMount(() => {
        loadCommands();
    });

    $: commandList = $commands;
    $: commandLookup = Object.fromEntries(commandList.map((command) => [command.id, command])) as Record<string, CommandDefinition>;
    $: activeJobId = $selectedJobId;
    $: activeLogs = activeJobId ? $jobLogs[activeJobId] ?? [] : [];

    async function handleLaunch(event: CustomEvent<{ commandId: string; params: Record<string, unknown> }>) {
        await launchJob(event.detail.commandId, event.detail.params);
    }

    function handleRefresh(): void {
        loadCommands();
    }

    async function handleSelect(event: CustomEvent<{ jobId: string }>): Promise<void> {
        await selectJob(event.detail.jobId);
    }

    $: bannerMessage = $jobError;

    function statusIndicatorClass(loading: boolean, error: string | null): string {
        if (error) return 'page__status-indicator page__status-indicator--error';
        if (loading) return 'page__status-indicator page__status-indicator--loading';
        return 'page__status-indicator';
    }
</script>

<svelte:head>
    <title>Crew Console</title>
</svelte:head>

<div class="page">
    <header class="page__header">
        <div>
            <p class="page__eyebrow">CrewAI Workflow Control</p>
            <h1>2510 YouTuber 制御パネル</h1>
            <p class="page__lead">
                デイリー自動生成ワークフローや検証コマンドを安全に実行し、ジョブ状況とログを一元監視します。
            </p>
        </div>
        <div class="page__status">
            <span class={statusIndicatorClass($commandsLoading, $commandsError)}>コマンド: {$commandsLoading ? '取得中…' : `${commandList.length}件`}</span>
            {#if bannerMessage}
                <button type="button" class="page__dismiss" on:click={clearJobMessage}>通知を閉じる</button>
            {/if}
        </div>
    </header>

    {#if bannerMessage}
        <div class="page__banner">
            <p>{bannerMessage}</p>
        </div>
    {/if}

    {#if $commandsError && !bannerMessage}
        <div class="page__warning">
            <p>{$commandsError}</p>
        </div>
    {/if}

    <main class="page__grid">
        <JobLauncher
            commands={commandList}
            loading={$commandsLoading}
            launching={$launchingJob}
            error={$commandsError}
            on:launch={handleLaunch}
            on:refresh={handleRefresh}
        />
        <JobMonitor
            jobs={$jobs}
            selectedJobId={activeJobId}
            logs={activeLogs}
            commands={commandLookup}
            on:select={handleSelect}
        />
    </main>
</div>

<style>
    :global(body) {
        margin: 0;
        font-family: 'Inter', 'Noto Sans JP', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background: radial-gradient(circle at top, rgba(30, 64, 175, 0.35), rgba(15, 23, 42, 0.95));
        color: #e2e8f0;
        min-height: 100vh;
    }

    .page {
        max-width: 1180px;
        margin: 0 auto;
        padding: 2.5rem 2rem 3rem;
        display: flex;
        flex-direction: column;
        gap: 2rem;
    }

    .page__header {
        display: flex;
        justify-content: space-between;
        gap: 2rem;
        align-items: flex-start;
    }

    .page__eyebrow {
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-size: 0.75rem;
        color: rgba(148, 163, 184, 0.75);
    }

    .page__header h1 {
        margin: 0.35rem 0 0;
        font-size: 2rem;
    }

    .page__lead {
        margin: 0.75rem 0 0;
        max-width: 46ch;
        color: rgba(226, 232, 240, 0.8);
        line-height: 1.6;
    }

    .page__status {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        align-items: flex-end;
    }

    .page__status-indicator {
        padding: 0.5rem 0.85rem;
        border-radius: 9999px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: rgba(15, 23, 42, 0.65);
        font-size: 0.85rem;
    }

    .page__status-indicator--loading {
        border-color: rgba(56, 189, 248, 0.35);
        color: #38bdf8;
    }

    .page__status-indicator--error {
        border-color: rgba(248, 113, 113, 0.45);
        color: #f87171;
    }

    .page__dismiss {
        border: none;
        background: transparent;
        color: rgba(226, 232, 240, 0.8);
        font-size: 0.8rem;
        cursor: pointer;
        text-decoration: underline;
    }

    .page__banner,
    .page__warning {
        padding: 0.85rem 1rem;
        border-radius: 14px;
        border: 1px solid;
        font-size: 0.9rem;
    }

    .page__banner {
        border-color: rgba(56, 189, 248, 0.45);
        background: rgba(56, 189, 248, 0.12);
        color: #38bdf8;
    }

    .page__warning {
        border-color: rgba(251, 191, 36, 0.45);
        background: rgba(251, 191, 36, 0.12);
        color: #fbbf24;
    }

    .page__grid {
        display: grid;
        grid-template-columns: 360px 1fr;
        gap: 1.75rem;
        align-items: start;
    }

    @media (max-width: 1080px) {
        .page__grid {
            grid-template-columns: 1fr;
        }

        .page__status {
            align-items: flex-start;
        }
    }

    @media (max-width: 640px) {
        .page {
            padding: 1.75rem 1.25rem 2.5rem;
        }

        .page__header {
            flex-direction: column;
        }

        .page__lead {
            max-width: 100%;
        }
    }
</style>
