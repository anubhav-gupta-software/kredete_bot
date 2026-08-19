import time




def test_normal_run(client):
    payload = {"goal": "test goal", "idempotency_key": "key-normal-1"}
    res = client.post('/runs', json=payload)
    assert res.status_code in (200,201)
    run = res.json()
    run_id = run['id']

    # poll until completed
    for _ in range(20):
        r = client.get(f'/runs/{run_id}')
        assert r.status_code == 200
        d = r.json()
        if d['status'] == 'completed':
            assert d['credits_used'] == 16
            return
        time.sleep(0.1)
    assert False, 'run did not complete in time'


def test_idempotent_retry(client):
    payload = {"goal": "test goal", "idempotency_key": "key-idem-1"}
    r1 = client.post('/runs', json=payload)
    assert r1.status_code in (200,201)
    r2 = client.post('/runs', json=payload)
    assert r2.status_code == 200
    assert r1.json()['id'] == r2.json()['id']


def test_forced_failure(client):
    payload = {"goal": "test fail", "idempotency_key": "key-fail-1", "simulate_failure_at_step": 2}
    res = client.post('/runs', json=payload)
    assert res.status_code in (200,201)
    run_id = res.json()['id']

    for _ in range(20):
        r = client.get(f'/runs/{run_id}')
        d = r.json()
        if d['status'] == 'failed':
            assert d['credits_used'] == 14
            return
        time.sleep(0.1)
    assert False, 'failed run did not finish in time'


def test_idempotency_conflict(client):
    # same idempotency key but different payload must return 409
    key = "key-conflict-1"
    payload1 = {"goal": "goal A", "idempotency_key": key}
    payload2 = {"goal": "goal B", "idempotency_key": key}
    r1 = client.post('/runs', json=payload1)
    assert r1.status_code in (200,201)
    r2 = client.post('/runs', json=payload2)
    assert r2.status_code == 409


def test_runaway_model_limits(client, monkeypatch):
    # Monkeypatch the model to always CALL_TOOL to simulate runaway behavior
    from app import mocks

    def always_call(step_number, goal, last_output):
        return mocks.Action.CALL_TOOL

    monkeypatch.setattr(mocks, 'decide_next_action', always_call)

    payload = {"goal": "runaway", "idempotency_key": "key-runaway-1"}
    res = client.post('/runs', json=payload)
    assert res.status_code in (200,201)
    run_id = res.json()['id']

    # wait until finished
    for _ in range(50):
        r = client.get(f'/runs/{run_id}')
        d = r.json()
        if d['status'] != 'running':
            # must end with STEP_LIMIT_REACHED and exactly MAX_STEPS steps
            assert d['error_code'] == 'STEP_LIMIT_REACHED'
            assert len(d['steps']) == 5
            assert d['credits_used'] == 35
            return
        time.sleep(0.1)
    assert False, 'runaway run did not finish in time'
