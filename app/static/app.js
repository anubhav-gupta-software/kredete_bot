async function startRun() {
  const goal = document.getElementById('goal').value
  const key = document.getElementById('key').value
  const failVal = document.getElementById('fail').value
  const payload = { goal, idempotency_key: key }
  if (failVal) payload.simulate_failure_at_step = parseInt(failVal)

  const res = await fetch('/runs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })
  const data = await res.json()
  const runId = data.id
  document.getElementById('status').innerText = `Run ${runId} - polling...`

  const interval = setInterval(async ()=>{
    const r = await fetch(`/runs/${runId}`)
    if (!r.ok) { clearInterval(interval); document.getElementById('status').innerText = 'Error fetching run'; return }
    const d = await r.json()
    document.getElementById('output').innerText = JSON.stringify(d, null, 2)
    if (d.status !== 'running') { clearInterval(interval); document.getElementById('status').innerText = `Run ${runId} - ${d.status}` }
  }, 500)
}

document.getElementById('start').addEventListener('click', startRun)
