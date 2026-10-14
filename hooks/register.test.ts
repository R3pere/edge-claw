import { expect, mock, test } from 'claude-code/testing'

const HINT = { isDraft: false, isWorking: false, hint: '? for shortcuts' }

for (const surface of ['terminal', 'desktop'] as const) {
  test(`hint line keeps the hint and offers the Clawd button on ${surface}`, async ($, on) => {
    mock.clock(on, { now: 1_000 })
    mock.env(on, { USERPROFILE: 'C:\\Users\\me' })
    on('fs.read', () => {
      throw new Error('ENOENT')
    })

    const ui = await $.ui.mount({
      plugin: 'edge-claw',
      surface,
      component: 'PromptHint',
      props: HINT as never,
    })
    expect(await ui.find({ text: /for shortcuts/ })).toBeTruthy()
    expect(await ui.find({ key: 'clawd' })).toBeTruthy()
  })
}

test('a permission ask raises the lightbulb until the call settles', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  mock.env(on, { USERPROFILE: 'C:\\Users\\me' })
  on('session.id', () => ({ value: 's1' }))
  const states: { attention: string | null }[] = []
  on('fs.write', (_$, e) => {
    states.push(JSON.parse(e.text))
    return { value: undefined }
  })
  on('tool.check', () => ({ decision: 'ask' as const }))
  on('tool.call', () => ({ result: 'ok' }) as never)

  await $.tool.check({ tool: 'Bash', input: { command: 'rm -rf build' }, tool_use_id: 't1' } as never)
  expect(states.at(-1)?.attention).toBe('permission')

  await $.tool.call({ tool: 'Bash', input: { command: 'rm -rf build' }, tool_use_id: 't1' } as never)
  expect(states.at(-1)?.attention).toBe(null)
})

test('a question to the person raises the lightbulb as a question', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  mock.env(on, { USERPROFILE: 'C:\\Users\\me' })
  on('session.id', () => ({ value: 's1' }))
  const states: { attention: string | null }[] = []
  let seenWhileAsking: string | null | undefined
  on('fs.write', (_$, e) => {
    states.push(JSON.parse(e.text))
    return { value: undefined }
  })
  on('tool.call', () => {
    seenWhileAsking = states.at(-1)?.attention
    return { result: 'answered' } as never
  })

  await $.tool.call({ tool: 'AskUserQuestion', input: { questions: [] }, tool_use_id: 'q1' } as never)
  expect(seenWhileAsking).toBe('question')
  expect(states.at(-1)?.attention).toBe(null)
})

test('a reply stopped with Esc tells Clawd it was interrupted', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  mock.env(on, { USERPROFILE: 'C:\\Users\\me' })
  const states: { status: string }[] = []
  on('fs.write', (_$, e) => {
    states.push(JSON.parse(e.text))
    return { value: undefined }
  })
  on('turn.complete', () => ({ text: '' }))

  await $.turn.complete({ answer: '', durationMs: 900, isAborted: true, turnId: 't1', reason: 'aborted' })
  expect(states.at(-1)?.status).toBe('interrupted')
})

test('each session keeps its own file: working through the turn, idle after', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  mock.env(on, { USERPROFILE: 'C:\\Users\\me' })
  on('session.id', () => ({ value: 's1' }))
  const writes: { path: string; state: { status: string; since?: number } }[] = []
  on('fs.write', (_$, e) => {
    writes.push({ path: e.path, state: JSON.parse(e.text) })
    return { value: undefined }
  })
  on('turn.start', () => ({ turnId: 't1' }) as never)
  on('turn.complete', () => ({ text: '' }))

  await $.turn.start({ text: 'hi', turnId: 't1' } as never)
  const started = writes.at(-1)
  expect(started?.path).toBe('C:\\Users\\me\\.claude\\edge-claw\\session-s1.json')
  expect(started?.state.status).toBe('working')
  expect(started?.state.since).toBe(1_000)

  await $.turn.complete({ answer: 'ok', durationMs: 900, isAborted: false, turnId: 't1', reason: 'answer' })
  expect(writes.find(w => w.path.endsWith('\state.json'))?.state.status).toBe('done')
  expect(writes.at(-1)?.path).toBe(started?.path)
  expect(writes.at(-1)?.state.status).toBe('idle')
})
