# Phemex market-data source and precision contract

Offline reproductions established three independent defects. Bare `BTC/USDT`
reached the spot market even for a swap request; changing only adapter.default_type
did not change the CCXT transport default. The direct REST fallback indexed raw
kline fields as if they were normalized OHLCV, reading interval as open and high
as close. Integer TICK_SIZE precision was interpreted as decimal-place precision.

The installed CCXT 4.5.49 `phemex.parse_ohlcv` and the [official Phemex kline
schema](https://github.com/phemex/phemex-api-docs/blob/master/Public-Hedged-Perpetual-API.md#query-kline)
agree on distinct interval/previous-close fields before OHLC. CCXT already owns
market-specific raw parsing and units. The hand-written fallback is removed from
the active fetch path; a failed normalized fetch now stays unavailable and uses
the existing bounded CCXT network/rate-limit retry. No new fallback endpoint or
scale inference is introduced. The old `_derive_fallback_scale` helper remains
test-only legacy code with no production caller, pending cleanup disposition.

Resolve public OHLCV/ticker/precision requests against loaded market metadata.
Plain pairs resolve to exactly one requested spot/swap market; qualified contracts
pin their identity. Missing or ambiguous markets reject before price transport.
The scanner synchronizes adapter and CCXT defaults through `set_market_type`.
Precision uses CCXT TICK_SIZE or DECIMAL_PLACES explicitly; unsupported/missing
values are unavailable, not zero constraints. The parent scanner carries failed
precision to the worker as unavailable and rejects before analysis. Adapters that
do not expose precision retain their existing optional-metadata behavior.

Upstream: scanner selected exchange/market and public metadata. Downstream:
ingestion cache identity, candles, indicator/regime/SMC computation, ticker reads,
planning geometry and existing live-entry precision validation. Changes are
limited to Phemex public data/metadata, scanner configuration and precision-failure
propagation; no order submission or execution protocol is altered.

Alternative: maintain a second raw protocol client with endpoint-specific parsing,
product price/quantity scales and failure policies. That duplicates CCXT and needs
separate protocol coverage. A guessed ticker ratio cannot verify raw field layout.
Removing the incorrect fallback is the smaller verified decision. Availability
may be lower when CCXT fails; returning corrupted candles is not an acceptable
availability mechanism. Revert source selection, precision and their callers
together if rolling back; never re-enable the faulty parser in isolation.

Verification: nine original market/fallback failures, four precision failures and
one consumer failure reproduced. Seventeen focused cases now pass; the expanded
selected backend suite passes 1,583 cases (31 existing deprecation warnings).
Contracts and eight smoke categories are clean. No exchange request, credential
use, historical-store write, bot start/restart or deployment occurred.
