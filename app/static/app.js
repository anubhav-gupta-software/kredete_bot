async function startRun() {
  const goal = document.getElementById('goal').value
  const key = document.getElementById('key').value
  const failVal = document.getElementById('fail').value
  const payload = { goal, idempotency_key: key }
  if (failVal) payload.simulate_failure_at_step = parseInt(failVal)

  const res = await fetch('/runs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })
  const data = await res.json()
  const runId = data.id
  const statusEl = document.getElementById('status')
  const creditsEl = document.getElementById('credits')
  const stepsEl = document.getElementById('steps')
  const finalEl = document.getElementById('final_output')

  statusEl.innerText = `Run ${runId} - polling...`

  const interval = setInterval(async ()=>{
    const r = await fetch(`/runs/${runId}`)
    if (!r.ok) { clearInterval(interval); statusEl.innerText = 'Error fetching run'; return }
    const d = await r.json()

    // update status and credits
    statusEl.innerText = `Run ${runId} - ${d.status}`
    creditsEl.innerText = d.credits_used || 0

    // update steps list
    stepsEl.innerHTML = ''
    if (Array.isArray(d.steps)){
      d.steps.forEach(s=>{
        const li = document.createElement('li')
        li.textContent = `${s.step_number}. ${s.action} ${s.tool?`(${s.tool})`:''} — ${s.status}`
        const sub = document.createElement('div')
        sub.style.color = '#374151'
        sub.style.fontSize = '13px'
        sub.textContent = s.output ? `Output: ${s.output}` : (s.error ? `Error: ${s.error}` : '')
        li.appendChild(sub)
        stepsEl.appendChild(li)
      })
    }

    // final output / error
    finalEl.innerText = d.output ? d.output : (d.error_message ? `${d.error_code||'ERROR'}: ${d.error_message}` : '')

    if (d.status !== 'running') { clearInterval(interval) }
  }, 500)
}

document.getElementById('start').addEventListener('click', startRun)
