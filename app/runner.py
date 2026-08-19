import json
import sqlite3
from app.db import get_connection
from app.mocks import (
    decide_next_action,
    mock_web_search,
    MODEL_ACTION_COST,
    WEB_SEARCH_COST,
    MAX_STEPS,
    Action,
)


def _sum_credits(conn, run_id):
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM credit_ledger WHERE run_id=?", (run_id,))
    row = cur.fetchone()
    return int(row["total"])


def _get_step_count(conn, run_id):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM steps WHERE run_id=?", (run_id,))
    return int(cur.fetchone()["c"])


def _insert_step_and_charges(conn, run_id, step_number, action, tool, input_text, charges):
    cur = conn.cursor()
    # start explicit transaction
    cur.execute("BEGIN")
    cur.execute(
        "INSERT INTO steps (run_id, step_number, action, tool, input, status) VALUES (?,?,?,?,?,?)",
        (run_id, step_number, action, tool, input_text, "running"),
    )
    # insert ledger entries
    for charge_type, amount in charges:
        try:
            cur.execute(
                "INSERT INTO credit_ledger (run_id, step_number, charge_type, amount) VALUES (?,?,?,?)",
                (run_id, step_number, charge_type, amount),
            )
        except sqlite3.IntegrityError:
            # duplicate charge, ignore
            pass
    conn.commit()


def _update_step(conn, run_id, step_number, status, output=None, error=None):
    cur = conn.cursor()
    cur.execute(
        "UPDATE steps SET status=?, output=?, error=? WHERE run_id=? AND step_number=?",
        (status, output, error, run_id, step_number),
    )
    conn.commit()


def _update_run(conn, run_id, status, output=None, error_code=None, error_message=None):
    cur = conn.cursor()
    cur.execute(
        "UPDATE runs SET status=?, output=?, error_code=?, error_message=?, updated_at=datetime('now') WHERE id=?",
        (status, output, error_code, error_message, run_id),
    )
    conn.commit()


def run_executor(run_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM runs WHERE id=?", (run_id,))
        run = cur.fetchone()
        if not run:
            return

        simulate_failure_at_step = run["simulate_failure_at_step"]
        goal = run["goal"]
        last_output = None

        while True:
            # check current step count
            step_count = _get_step_count(conn, run_id)
            if step_count >= MAX_STEPS:
                _update_run(conn, run_id, "failed", None, "STEP_LIMIT_REACHED", "Max steps reached")
                return

            next_step_number = step_count + 1

            # model action charge
            charges = [("MODEL_ACTION", MODEL_ACTION_COST)]

            action = decide_next_action(next_step_number, goal, last_output)

            if action == Action.CALL_TOOL:
                # charge model action and tool attempt atomically with step row
                charges.append(("WEB_SEARCH", WEB_SEARCH_COST))
                _insert_step_and_charges(conn, run_id, next_step_number, action.value, "web_search", goal, charges)

                # execute tool outside txn
                try:
                    simulate = (simulate_failure_at_step == next_step_number)
                    result = mock_web_search(goal, simulate_failure=simulate)
                    _update_step(conn, run_id, next_step_number, "completed", output=result)
                    last_output = result
                    # continue loop
                    continue
                except Exception as e:
                    _update_step(conn, run_id, next_step_number, "failed", output=None, error=str(e))
                    _update_run(conn, run_id, "failed", None, "TOOL_ERROR", str(e))
                    return

            else:
                # FINISH: charge model action and write final output
                _insert_step_and_charges(conn, run_id, next_step_number, action.value, None, goal, charges)
                final_output = f"final_output_based_on:{goal}"
                _update_step(conn, run_id, next_step_number, "completed", output=final_output)
                _update_run(conn, run_id, "completed", final_output, None, None)
                return

    finally:
        conn.close()
