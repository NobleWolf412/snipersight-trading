# Windows checkpoint replacement and isolated verification

Date: 2026-10-07 (operator date, America/New_York).

## Authorization and bounded change

The operator approved the first implementation batch after reviewing the discovery checkpoint: fix `PaperTradingService._save_state`, verify repeated saves and failure handling, and run the required audits. The production change is only `Path.rename` to `Path.replace` plus its comment/docstring. No order, threshold, sizing, credential, session-restart or journal-schema change is authorized by this batch. No commit, push, deployment or live order was made.

## Root cause and evidence

On this Windows host, renaming a temporary file over an existing checkpoint raises `FileExistsError` / WinError 183. The first save succeeds; subsequent saves leave `state.json` stale and the latest data in `state.tmp`. The existing warning is retained. Publication now replaces the destination from the same directory.

The source method is extracted through AST and executed without importing the service module. The offline fixture uses an empty position/order set and temporary files. Seven checks exercise first write, repeated write, removal of the published temp file, attempted denied publication, byte-identical retention of the previous checkpoint, warning emission, and successful retry. Before the source edit 4/7 passed; afterward 7/7 passed. This is direction-agnostic persistence verification, not a bull/bear trading test, complete crash recovery, multi-writer synchronization or power-loss durability guarantee.

Upstream callers: `stop`, the filled/open branch of `_process_signal`, and `_sync_closed_positions`, all in `paper_trading_service.py`. The method describes restore as manual/future. Search found no application reader of `state.json`; frontend status reads service HTTP state. The standalone diagnostic is a reader added by this audit. Shared/testnet paper sessions can use this writer; live-service order execution was not edited.

## Verification trap and isolation

`capture_contracts diff` is not side-effect-free: importing `api_server` loads dotenv, creates an exchange adapter that attempts `load_markets`, and initializes a telemetry store. The reviewer inspected these paths before running anything. Unrestricted execution was not used.

The actual, unchanged driver ran in a disposable subprocess under a temporary verification harness. It clears inherited environment except OS/path/temp essentials, disables dotenv, denies network/process creation and `.env` reads, and confines writes to a temporary directory. The real `TelemetryStorage` constructor receives a temporary `db_path`; route registration and domain classes remain real. The actual `pipeline_smoke verify` runs under the same guard. Blocked adapter initialization calls are expected; these are structural checks only, not exchange or application-lifecycle tests. No production data integration was changed or substituted.

The reproducible harness source, hash, exact commands and full baseline/post output are retained in `docs/audits/SYSTEM_DISCOVERY_2026-10-07_evidence.json` under `checkpoint_fix.backend_integrity`. The original temporary harness path is also recorded. The isolated invocation is not presented as an unrestricted production-environment check.

## Existing contract drift, not re-baselined

Both before and after the patch:

- API, telemetry and pipeline contract sections are clean.
- Contract command exits **1**, with one DB/JSONL delta: the first-row keys of `backend/cache/trade_journal.jsonl` differ from the 45-key baseline; the current first row has 25 keys.
- Pipeline smoke exits **0**, all eight structural checks clean.

The runtime journal has 384 rows. Its last row has 55 keys and includes every baseline key. This is heterogeneous historical data plus first-row sampling, not a new writer migration from this patch. The same sampling limitation and a prior 45-key baseline are documented at `2026-06-13__journal-entry-pool-instrumentation.md:80-96`.

**Downstream-update disposition:** none required by this patch; the checkpoint payload and journal producers/consumers are unchanged, and the delta is identical before/after. This documents the existing delta for rubric review; it does not turn a nonzero contract command into a clean result or waive the literal clean-contract gate. Do not alter historical journal records or regenerate contract snapshots merely to get a green check. A durable schema-sampling correction or an explicit gate exception requires a separate decision/authorization.

## Edit fidelity and rollback

The semantic edit used Serena. Serena rewrote LF to CRLF; original LF was restored after verifying that reversing the intended patch yields the exact original HEAD bytes. The production diff contains only the publication operation, explanatory comment and docstring. Post-contract verification preceded this newline restoration; the Python semantics are identical. The final diagnostic records the final source hash.

Rollback is a targeted reversal of the production diff. Preserve historical session files, the original discovery hashes and failing reproduction; do not rewrite runtime checkpoints as part of this fix.
