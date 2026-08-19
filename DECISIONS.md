DECISIONS

- MAX_STEPS = 5 to bound runaway loops. Runner enforces this before creating a new step.
- Credits are integers only. MODEL_ACTION_COST=2, WEB_SEARCH_COST=5. Charges are recorded when work is attempted (no refunds).
- Idempotency: DB-level UNIQUE on `idempotency_key`. We compute a `request_hash` (canonical JSON excluding idempotency_key) and store it. If the same idempotency_key is reused with a different request_hash we return 409. Only the request that successfully inserts the run starts the runner.
- Database: raw sqlite3, WAL mode enabled. A new connection per thread is used.
- Limitations: single-process runner. If process crashes after run insert the run may be left in `running` but unprocessed.
