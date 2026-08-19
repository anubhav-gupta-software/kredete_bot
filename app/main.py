from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import hashlib

from app.db import init_db, get_connection
from app.runner import run_executor


app = FastAPI()

# Ensure DB initialized at import time (helps tests using TestClient)
init_db()


class RunRequest(BaseModel):
    goal: str
    idempotency_key: str
    simulate_failure_at_step: Optional[int] = None


def compute_request_hash(payload: dict) -> str:
    # exclude idempotency_key
    payload_copy = {k: v for k, v in payload.items() if k != "idempotency_key"}
    canonical = json.dumps(payload_copy, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@app.on_event("startup")
def startup():
    init_db()


@app.post("/runs")
def create_run(req: RunRequest, background_tasks: BackgroundTasks):
    conn = get_connection()
    cur = conn.cursor()
    req_dict = req.dict()
    request_hash = compute_request_hash(req_dict)

    try:
        cur.execute(
            "INSERT INTO runs (idempotency_key, request_hash, goal, status, simulate_failure_at_step) VALUES (?,?,?,?,?)",
            (req.idempotency_key, request_hash, req.goal, "running", req.simulate_failure_at_step),
        )
        conn.commit()
        run_id = cur.lastrowid
        # start runner in background
        background_tasks.add_task(run_executor, run_id)
        cur.execute("SELECT id, idempotency_key, goal, status, created_at, request_hash FROM runs WHERE id=?", (run_id,))
        row = cur.fetchone()
        return dict(row)
    except Exception as e:
        # likely UNIQUE constraint on idempotency_key
        conn.rollback()
        cur.execute("SELECT * FROM runs WHERE idempotency_key=?", (req.idempotency_key,))
        existing = cur.fetchone()
        if existing:
            if existing["request_hash"] == request_hash:
                # idempotent replay, return existing run
                return dict(existing)
            else:
                raise HTTPException(status_code=409, detail="Idempotency key already used with different request")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM runs WHERE id=?", (run_id,))
    run = cur.fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # fetch steps
    cur.execute(
        "SELECT step_number, action, tool, input, output, status, error, created_at FROM steps WHERE run_id=? ORDER BY step_number",
        (run_id,),
    )
    steps = [dict(r) for r in cur.fetchall()]

    # compute credits used
    cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM credit_ledger WHERE run_id=?", (run_id,))
    total = int(cur.fetchone()["total"])

    resp = {
        "id": run["id"],
        "goal": run["goal"],
        "status": run["status"],
        "credits_used": total,
        "steps": steps,
        "output": run["output"],
        "error_code": run["error_code"],
        "error_message": run["error_message"],
    }
    conn.close()
    return resp
