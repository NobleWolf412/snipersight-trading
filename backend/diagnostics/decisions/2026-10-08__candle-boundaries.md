# Candle boundaries and grid preservation

Seven offline counterexamples expose four ingestion failures: Monday weekly rows are reindexed onto pandas' Sunday weekly grid and lost; epoch-floor weekly close checks use a Thursday anchor and can admit unfinished weeks; stripping only the final row leaves earlier future/incomplete rows; duplicate timestamps fail reindexing before the documented duplicate policy runs. An off-grid observation can also disappear during reindexing without an explicit rejection.

Bounded decision: use fixed seven-day increments anchored to the supplied first weekly open; resolve duplicate timestamps using the existing keep-first policy before reindex; reject off-grid source rows rather than discard them; include each known-duration candle only when its own open plus duration is at or before the captured clock. A failed close-time calculation rejects that timeframe through the existing logged ingestion failure path. Preserve the existing synthetic flat/zero-volume gap policy and all score/gate thresholds.

Blast radius: exchange adapter OHLCV (Phemex explicitly converts millisecond epochs into timestamps) -> `IngestionPipeline.normalize_and_validate` -> shared cache -> indicators/SMC/global and symbol regimes/scoring/planning, scanner/bot and replay window fetch. Changes are confined to ingestion and regression tests. This restores the intended closed-candle/data-preservation contract and can change signals that previously consumed corrupt/incomplete input.

Alternatives: force a universal weekly weekday (still wrong for a feed with another supplied anchor), or disable gap filling altogether (changes indicator sample spacing and broader strategy behavior). Keep the feed anchor and reject inconsistent rows instead. Rollback is this bounded normalization diff; never substitute historical cache rows to make validation pass.

Verification covers supplied weekly anchors, exact close boundary, multiple future rows, duplicate timestamps, off-grid rejection, missing-week fill, and existing intraday/cache tests. Monthly case normalization and source identity in the shared cache are separate open questions. No historical store changes or network calls.

Verification completed: seven original failures; eleven new cases and 42 combined timing/cache/scanner tests pass. Source input is unchanged, Monday and Sunday weekly feeds retain their anchors, exact-close rows are retained, invalid clocks reject visibly. Four contract inventories and eight smoke categories compare clean.
