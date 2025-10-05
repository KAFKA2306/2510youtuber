# 2025-10-05 Workflow Regression Investigation

## Incident summary
- **Symptom:** The CrewAI workflow began failing during the `video_generation` step at 14:04 JST, emitting repeated `ffmpeg` errors for both the primary render and the fallback video path.
- **Last known good:** Runs completed successfully at 12:58 JST on the same day.
- **Impact:** End-to-end automation halted because the fallback renderer also crashed, leaving no deliverable video artifact.

## Commit timeline between 12:58 JST and 14:04 JST
The window between the healthy and failing executions contains a dense batch of merges. The excerpt below highlights the most relevant entries:

| Commit | Time (JST) | Notes |
| --- | --- | --- |
| `4e0fc35` → `5bd8dc0` | 13:07–13:11 | Prompt helper refactors, no runtime impact. |
| `e286714` | 13:13 | Prompt default centralisation (config/docs only). |
| `9f676e4` | 13:46 | Adds subtitle-burning logic to the fallback renderer and new tests. |
| `c5bb00c` | 13:54 | Major refactor folding B-roll pre-generation into `VideoGenerator` and `GenerateVideoStep`. |
| `afc63e6`, `f57a016` | 13:56 | Merge wrappers for the above feature work. |

`git log` confirms that `app/video.py` only changed in this window via `9f676e4` and the large `c5bb00c` refactor, while the surrounding commits touch prompts, docs, or metadata plumbing.【a35ea0†L1-L18】【f6d67f†L1-L5】

## Findings
1. **Environment drifted away from a system ffmpeg binary.**
   - `which ffmpeg` now resolves to nothing inside the runtime container, meaning `ffmpeg-python` cannot rely on the bare `ffmpeg` executable name.【fe1b4b†L1-L2】
   - Executing the compiled render command verbatim demonstrates the failure: the shell reports `command not found: ffmpeg` when the binary name is not fully qualified.【4a1032†L5-L10】【b27770†L1-L5】
2. **`VideoGenerator` already resolves a working binary via `ensure_ffmpeg_tooling`.**
   - Construction of the generator hydrates `self.ffmpeg_path` with the validated imageio shim, and all renders flow through `_run_ffmpeg` after the follow-up fix.【a2658a†L160-L190】【532e58†L807-L829】
3. **Root cause is not limited to B-roll changes.**
   - Although `c5bb00c` reshaped B-roll orchestration, the decisive break was the environment’s missing `ffmpeg` shim on `$PATH`; prior runs succeeded because the binary happened to be globally available. Once it disappeared, every `ffmpeg.run(...)` call that relied on the default command string began failing, including the fallback renderer introduced in `9f676e4`.

## Resolution status
- The latest patch (`cfce931`) routes every `ffmpeg.run` call through `_run_ffmpeg`, which now injects `self.ffmpeg_path` so the validated binary is always executed, even when `$PATH` lacks `ffmpeg`.【532e58†L807-L829】
- No additional regressions surfaced in adjacent modules during the investigation window; non-media commits in the log affect prompts, docs, or metadata tracking only.【a35ea0†L1-L18】

## Recommended follow-ups
1. Add a lightweight startup check (e.g., `ffmpeg -version` through `ensure_ffmpeg_tooling`) to fail fast when configuration drifts.
2. Keep `VideoGenerator` smoke tests around the fallback renderer so subtitle changes (like `9f676e4`) stay covered.
3. Document the dependency on `imageio-ffmpeg` in the deployment guide to avoid future PATH regressions.
