import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Attention, PetStatus } from '../types'

const isOut = atom({ plugin: 'edge-claw', key: 'isOut' } as const, false)

let status: PetStatus = 'idle'

// Tool calls waiting on the person: a permission dialog, or a question or plan
// put to them. Clawd holds up its lightbulb while any is open.
const waiting = new Map<string, Attention>()

// Tools whose ask is a question to answer, not a permission to grant.
const QUESTION_TOOLS = new Set(['AskUserQuestion', 'ExitPlanMode'])

function attention(): Attention | null {
  const kinds = [...waiting.values()]
  if (kinds.includes('question')) return 'question'
  return kinds.length > 0 ? 'permission' : null
}

async function petHome($: EngineInterface): Promise<string> {
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME')) ?? ''
  return `${home}\\.claude\\edge-claw`
}

// The pet writes alive.json every second while it is out.
async function isPetOut($: EngineInterface): Promise<boolean> {
  try {
    const alive = JSON.parse(await $.fs.read(`${await petHome($)}\\alive.json`))
    return (await $.clock.now()) - Number(alive.ts) < 3000
  } catch {
    return false
  }
}

async function writeState($: EngineInterface, extra: Record<string, unknown>): Promise<void> {
  try {
    const ts = await $.clock.now()
    const state = { status, attention: attention(), ts, ...extra }
    await $.fs.write(`${await petHome($)}\\state.json`, JSON.stringify(state))
  } catch {
    // the pet just keeps doing what it was doing
  }
}

async function findPythonw($: EngineInterface): Promise<string> {
  const local = await $.env.get('LOCALAPPDATA')
  if (local) {
    try {
      const dir = `${local}\\Programs\\Python`
      const versions = (await $.fs.list(dir))
        .filter(entry => entry.kind === 'directory' && entry.name.startsWith('Python3'))
        .map(entry => entry.name)
        .sort()
        .reverse()
      for (const name of versions) {
        const exe = `${dir}\\${name}\\pythonw.exe`
        if (await $.fs.exists(exe)) return exe
      }
    } catch {
      // fall through to the launcher
    }
  }
  if (await $.fs.exists('C:\\Windows\\pyw.exe')) return 'C:\\Windows\\pyw.exe'
  return 'pythonw'
}

async function letOut($: EngineInterface): Promise<string | null> {
  const pythonw = await findPythonw($)
  const script = `${$.plugin.root}\\pet\\clawd.pyw`.replaceAll('/', '\\')
  const quote = (s: string) => s.replaceAll("'", "''")
  // WMI creates the pet as the system's child, not Claude's: outside the job the
  // Claude app runs its processes in, which Windows closes when the app updates
  // or restarts, so Clawd outlives Claude instead of vanishing with it.
  const commandLine = `"${pythonw}" "${script}"`
  try {
    const ran = await $.process.run([
      'powershell.exe',
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      `$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = '${quote(commandLine)}' }; ` +
        'if ($r.ReturnValue -ne 0) { Write-Error "Win32_Process.Create returned $($r.ReturnValue)"; exit 1 }',
    ])
    return ran.exitCode === 0 ? null : ran.stderr.trim() || `exit code ${ran.exitCode}`
  } catch (error) {
    return String(error)
  }
}

async function toggle($: EngineInterface): Promise<string> {
  if (await isPetOut($)) {
    await writeState($, { cmd: 'quit', cmdId: await $.clock.now() })
    await update($, isOut, () => false)
    return 'Clawd 回去休息了。'
  }
  const failure = await letOut($)
  if (failure) {
    $.ui.toast(`Clawd 没能出来：${failure}`)
    return `Clawd 没能出来：${failure}`
  }
  await update($, isOut, () => true)
  return 'Clawd 出来啦，在任务栏上方。'
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'clawd',
      description: '召唤或收起桌面上的小 Clawd',
    })
    await update($, isOut, () => false)
    void isPetOut($).then(out => update($, isOut, () => out))

    return next(e)
  })

  on('command.run', { command: 'clawd' }, async $ => ({ text: await toggle($) }))

  // Main-loop turns only: a subagent's run raises no turn.start.
  on('turn.start', async ($, e, next) => {
    status = 'working'
    await writeState($, {})

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (!e.agentId) {
      waiting.clear()
      status = e.reason === 'answer' ? 'done' : 'interrupted'
      await writeState($, { durationMs: e.durationMs })  // a long task earns confetti
      status = 'idle'
    }

    return next(e)
  })

  // A call the engine puts to the person (a permission dialog, a question, a
  // plan to approve) waits on them until its tool.call settles below.
  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask' && e.tool_use_id) {
      waiting.set(e.tool_use_id, QUESTION_TOOLS.has(e.tool) ? 'question' : 'permission')
      await writeState($, {})
    }

    return verdict
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    if (QUESTION_TOOLS.has(e.tool) && !waiting.has(e.tool_use_id)) {
      waiting.set(e.tool_use_id, 'question')
      await writeState($, {})
    }
    try {
      return await next(e)
    } finally {
      if (waiting.delete(e.tool_use_id)) await writeState($, {})
    }
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'PromptHint' }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const out = await read($, isOut)

    return (
      <Box>
        <Text dimColor wrap="truncate">
          {e.props.hint}
        </Text>
        <Text> </Text>
        <Button
          key="clawd"
          label={out ? '🦀 收起 Clawd' : '🦀 召唤 Clawd'}
          plain
          onPress={() => void toggle($)}
        />
      </Box>
    )
  })
}
