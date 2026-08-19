import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_normal_run():
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


def test_idempotent_retry():
    payload = {"goal": "test goal", "idempotency_key": "key-idem-1"}
    r1 = client.post('/runs', json=payload)
    assert r1.status_code in (200,201)
    r2 = client.post('/runs', json=payload)
    assert r2.status_code == 200
    assert r1.json()['id'] == r2.json()['id']


def test_forced_failure():
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
