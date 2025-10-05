<script lang="ts">
    import { createEventDispatcher, onMount } from 'svelte';
    import type { CommandDefinition, CommandParameterSchema } from '$lib/types';

    export let commands: CommandDefinition[] = [];
    export let loading = false;
    export let launching = false;
    export let error: string | null = null;

    const dispatch = createEventDispatcher<{
        launch: { commandId: string; params: Record<string, unknown> };
        refresh: void;
    }>();

    let selectedCommandId: string | null = null;
    let params: Record<string, unknown> = {};
    let paramsVersion = '';

    onMount(() => {
        if (!selectedCommandId && commands.length > 0) {
            selectedCommandId = commands[0].id;
        }
    });

    $: if (!selectedCommandId && commands.length > 0) {
        selectedCommandId = commands[0].id;
    }

    $: selectedCommand = commands.find((cmd) => cmd.id === selectedCommandId) ?? null;

    $: {
        const versionKey = selectedCommand ? selectedCommand.id : '';
        if (versionKey !== paramsVersion) {
            params = buildDefaultParams(selectedCommand?.params_schema);
            paramsVersion = versionKey;
        }
    }

    $: parameterEntries = Object.entries(selectedCommand?.params_schema?.properties ?? {});
    $: requiredSet = new Set(selectedCommand?.params_schema?.required ?? []);

    function buildDefaultParams(schema?: CommandParameterSchema | undefined): Record<string, unknown> {
        if (!schema || schema.type !== 'object' || !schema.properties) {
            return {};
        }
        const defaults: Record<string, unknown> = {};
        for (const [key, definition] of Object.entries(schema.properties)) {
            if (definition.default !== undefined) {
                defaults[key] = definition.default;
            } else if (definition.enum && definition.enum.length > 0) {
                defaults[key] = definition.enum[0];
            } else if (definition.type === 'boolean') {
                defaults[key] = false;
            } else if (definition.type === 'number' || definition.type === 'integer') {
                defaults[key] = 0;
            } else {
                defaults[key] = '';
            }
        }
        return defaults;
    }

    function handleSubmit(event: Event): void {
        event.preventDefault();
        if (!selectedCommandId) {
            return;
        }
        dispatch('launch', { commandId: selectedCommandId, params });
    }

    function updateParam(key: string, value: unknown): void {
        params = { ...params, [key]: value };
    }

    function asString(value: unknown): string {
        if (value === null || value === undefined) {
            return '';
        }
        return String(value);
    }

    function parseNumber(value: string): number | null {
        if (value.trim() === '') {
            return null;
        }
        const parsed = Number(value);
        return Number.isNaN(parsed) ? null : parsed;
    }
</script>

<section class="launcher">
    <header class="launcher__header">
        <div>
            <h2>ジョブランチャー</h2>
            <p class="launcher__subtitle">CrewAIワークフローや検証コマンドを1クリックで起動します。</p>
        </div>
        <button class="ghost" type="button" on:click={() => dispatch('refresh')} disabled={loading}>
            {loading ? '更新中…' : 'コマンド再取得'}
        </button>
    </header>

    {#if error}
        <div class="launcher__alert">
            <p>{error}</p>
        </div>
    {/if}

    <form class="launcher__form" on:submit={handleSubmit}>
        <label class="launcher__label" for="command">コマンド</label>
        <select
            id="command"
            bind:value={selectedCommandId}
            disabled={loading || launching || commands.length === 0}
        >
            {#each commands as command}
                <option value={command.id}>{command.label}</option>
            {/each}
        </select>

        {#if selectedCommand}
            <p class="launcher__description">{selectedCommand.description}</p>
        {/if}

        {#if parameterEntries.length > 0}
            <div class="launcher__parameters">
                <h3>パラメータ</h3>
                <ul>
                    {#each parameterEntries as [key, schema]}
                        <li>
                            <label for={`param-${key}`}>
                                <span class="param-label">{schema.title ?? key}</span>
                                {#if schema.description}
                                    <span class="param-help">{schema.description}</span>
                                {/if}
                                {#if requiredSet.has(key)}
                                    <span class="param-required">必須</span>
                                {/if}
                            </label>

                            {#if schema.enum}
                                <select
                                    id={`param-${key}`}
                                    value={asString(params[key])}
                                    on:change={(event) => updateParam(key, (event.target as HTMLSelectElement).value)}
                                >
                                    {#each schema.enum as choice}
                                        <option value={choice}>{choice}</option>
                                    {/each}
                                </select>
                            {:else if schema.type === 'boolean'}
                                <label class="checkbox">
                                    <input
                                        id={`param-${key}`}
                                        type="checkbox"
                                        checked={Boolean(params[key])}
                                        on:change={(event) => updateParam(key, (event.target as HTMLInputElement).checked)}
                                    />
                                    <span>有効にする</span>
                                </label>
                            {:else if schema.type === 'number' || schema.type === 'integer'}
                                <input
                                    id={`param-${key}`}
                                    type="number"
                                    value={asString(params[key])}
                                    on:input={(event) => updateParam(key, parseNumber((event.target as HTMLInputElement).value))}
                                />
                            {:else}
                                <input
                                    id={`param-${key}`}
                                    type="text"
                                    value={asString(params[key])}
                                    on:input={(event) => updateParam(key, (event.target as HTMLInputElement).value)}
                                />
                            {/if}
                        </li>
                    {/each}
                </ul>
            </div>
        {/if}

        <div class="launcher__actions">
            <button type="submit" class="primary" disabled={launching || loading || !selectedCommandId}>
                {launching ? '起動中…' : 'ジョブを開始'}
            </button>
        </div>
    </form>
</section>

<style>
    .launcher {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
        padding: 1.5rem;
        border-radius: 16px;
        background: rgba(17, 24, 39, 0.92);
        color: #f9fafb;
        box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.55);
    }

    .launcher__header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
    }

    .launcher__header h2 {
        margin: 0;
        font-size: 1.5rem;
    }

    .launcher__subtitle {
        margin: 0.25rem 0 0;
        font-size: 0.95rem;
        color: rgba(226, 232, 240, 0.85);
    }

    .launcher__alert {
        padding: 0.75rem 1rem;
        border-radius: 12px;
        background: rgba(251, 191, 36, 0.1);
        border: 1px solid rgba(251, 191, 36, 0.4);
        color: #facc15;
        font-size: 0.9rem;
    }

    .launcher__form {
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
    }

    .launcher__label {
        font-weight: 600;
        font-size: 0.95rem;
    }

    select,
    input[type='text'],
    input[type='number'] {
        width: 100%;
        padding: 0.65rem 0.75rem;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.4);
        background: rgba(15, 23, 42, 0.85);
        color: #e2e8f0;
        font-size: 0.95rem;
    }

    select:focus,
    input:focus {
        outline: none;
        border-color: #38bdf8;
        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25);
    }

    .launcher__description {
        margin: -0.5rem 0 0;
        font-size: 0.9rem;
        color: rgba(226, 232, 240, 0.75);
    }

    .launcher__parameters ul {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .launcher__parameters h3 {
        margin: 0 0 0.5rem;
        font-size: 1.05rem;
    }

    .param-label {
        font-weight: 600;
        display: block;
    }

    .param-help {
        display: block;
        font-size: 0.8rem;
        color: rgba(226, 232, 240, 0.6);
        margin-top: 0.25rem;
    }

    .param-required {
        background: rgba(248, 113, 113, 0.15);
        border: 1px solid rgba(248, 113, 113, 0.4);
        color: #f87171;
        border-radius: 9999px;
        font-size: 0.7rem;
        padding: 0.1rem 0.5rem;
        margin-left: 0.5rem;
    }

    .checkbox {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.95rem;
    }

    .checkbox input {
        width: auto;
        accent-color: #38bdf8;
    }

    .launcher__actions {
        display: flex;
        justify-content: flex-end;
    }

    button.primary {
        padding: 0.7rem 1.4rem;
        border-radius: 12px;
        border: none;
        background: linear-gradient(135deg, #38bdf8, #6366f1);
        color: white;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    button.primary:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        box-shadow: none;
    }

    button.primary:not(:disabled):hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 30px -10px rgba(56, 189, 248, 0.6);
    }

    button.ghost {
        padding: 0.55rem 1rem;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.4);
        background: transparent;
        color: rgba(226, 232, 240, 0.9);
        cursor: pointer;
        font-weight: 500;
    }

    button.ghost:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    button.ghost:not(:disabled):hover {
        border-color: rgba(148, 163, 184, 0.8);
    }
</style>
