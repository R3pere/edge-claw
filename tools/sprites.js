#!/usr/bin/env node
// Clawd's sprites, decoded from the Claude desktop app installed on this computer.
//
// The app's Clawd mini-game (clawdQuestEngine-*.js inside resources/app.asar)
// carries 25 pixel animations as a table: each a palette, a base frame of
// palette indexes (base 36, "." transparent) and per-frame deltas. This reads
// that table straight from the installed app and writes what the pet uses.
//
//   node tools/sprites.js extract          write pet/clawd_sprites.json (the clips in USED)
//   node tools/sprites.js list             every clip in the app: size, frames, anchor
//   node tools/sprites.js gallery out.html  an HTML page playing every clip
//   node tools/sprites.js frames out.png Name [Name...]  every frame of some clips, numbered by position
//   node tools/sprites.js ids Name [Name...]  each frame's distinct-picture id, to find loops
//
// The artwork is Anthropic's: it stays on this machine and out of git.

const fs = require('fs')
const path = require('path')
const zlib = require('zlib')

const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'pet', 'clawd_sprites.json')

// The clips the pet plays. Add a name here, then run `extract`.
const USED = [
  'CrabWalking', 'LookingAround', 'LookingAroundEyesOnly', 'Waving', 'Dizzy',
  'Thinking', 'Laptop', 'Desktop', 'Lightbulb', 'JumpingHappy', 'Jumping', 'Excited',
  'Facepalm', 'Pointing', 'Disappointed', 'DancingHappy', 'Hula', 'Swaying', 'BreakDancing',
  'Confetti', 'Spark', 'Meditating',
]

// The app is a Store (MSIX) package: WindowsApps can't be listed, but Windows
// says where the installed version lives.
function findAsar() {
  const { execFileSync } = require('child_process')
  const where = execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
    "(Get-AppxPackage -Name 'Claude' | Sort-Object Version | Select-Object -Last 1).InstallLocation"],
  { encoding: 'utf8' }).trim()
  const asar = path.join(where, 'app', 'resources', 'app.asar')
  if (!where || !fs.existsSync(asar)) throw new Error('Claude desktop app not found (Get-AppxPackage Claude: "' + where + '")')
  return asar
}

// asar: a 16-byte prefix, a JSON header of the file tree, then the files back to back
function readFromAsar(asar, match) {
  const fd = fs.openSync(asar, 'r')
  const head = Buffer.alloc(16)
  fs.readSync(fd, head, 0, 16, 0)
  const size = head.readUInt32LE(12)
  const json = Buffer.alloc(size)
  fs.readSync(fd, json, 0, size, 16)
  const tree = JSON.parse(json.toString('utf8'))
  const base = 8 + head.readUInt32LE(4)
  let found = null
  ;(function walk(node, at) {
    for (const [name, entry] of Object.entries(node.files || {})) {
      if (entry.files) walk(entry, at + '/' + name)
      else if (!found && match.test(name) && !entry.unpacked) found = { at: at + '/' + name, entry }
    }
  })(tree, '')
  if (!found) throw new Error('no file matching ' + match + ' in ' + asar)
  const buf = Buffer.alloc(found.entry.size)
  fs.readSync(fd, buf, 0, buf.length, base + Number(found.entry.offset))
  fs.closeSync(fd)
  return { name: found.at, text: buf.toString('utf8') }
}

// The sprite table is an object literal `{BreakDancing:{cat:...},...}`: find its
// first entry, walk to the matching brace, and evaluate that literal (data only).
function spriteTable(engine) {
  const first = engine.search(/[A-Za-z0-9_]+:\{cat:"[A-Za-z]+",w:\d+,h:\d+/)
  if (first < 0) throw new Error('sprite table not found: the app may have changed its format')
  const start = engine.lastIndexOf('{', first)
  let depth = 0, quote = null, i = start
  for (; i < engine.length; i++) {
    const c = engine[i]
    if (quote) { if (c === '\\') i++; else if (c === quote) quote = null; continue }
    if (c === '"' || c === "'" || c === '`') { quote = c; continue }
    if (c === '{') depth++
    else if (c === '}' && --depth === 0) break
  }
  return Function('return ' + engine.slice(start, i + 1))()
}

// As the game does: the base frame, then each delta ("<pos base36><index>" pairs) applied in turn.
function decode(t) {
  const frames = []
  const px = [...t.base].map(c => (c === '.' ? 255 : parseInt(c, 36)))
  frames.push(px.slice())
  for (const d of t.deltas) {
    if (d) for (const p of d.split(',')) {
      const k = p.length - 1
      px[parseInt(p.slice(0, k), 36)] = p[k] === '.' ? 255 : parseInt(p[k], 36)
    }
    frames.push(px.slice())
  }
  const a0 = t.a0[2] > 0 ? t.a0 : [0, 0, t.w, t.h] // the body's box: the anchor is its bottom centre
  return {
    w: t.w, h: t.h, fps: t.fps, palette: t.palette, ax: a0[0] + a0[2] / 2, ay: a0[1] + a0[3],
    frames: frames.map(f => f.map(v => (v === 255 ? '.' : v.toString(36))).join('')),
  }
}

function loadAll() {
  const asar = findAsar()
  const engine = readFromAsar(asar, /^clawdQuestEngine-.*\.js$/)
  const table = spriteTable(engine.text)
  const all = {}
  for (const [name, t] of Object.entries(table)) all[name] = decode(t)
  return { asar, all }
}

function writePng(file, W, H, px) {
  const raw = Buffer.alloc((W * 3 + 1) * H)
  for (let y = 0; y < H; y++) px.copy(raw, y * (W * 3 + 1) + 1, y * W * 3, (y + 1) * W * 3)
  const table = []
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; table[n] = c >>> 0 }
  const crc = b => { let x = 0xffffffff; for (const v of b) x = table[(x ^ v) & 255] ^ (x >>> 8); return (x ^ 0xffffffff) >>> 0 }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length)
    const body = Buffer.concat([Buffer.from(type), data]); const sum = Buffer.alloc(4); sum.writeUInt32BE(crc(body))
    return Buffer.concat([len, body, sum])
  }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4); ihdr[8] = 8; ihdr[9] = 2
  fs.writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]))
}

// Every frame of the named clips, 10 to a row, scaled 3x on grey, cells outlined.
function framesSheet(all, names, file) {
  const S = 3, PER = 10
  const cw = Math.max(...names.map(n => all[n].w)) * S + 6, ch = Math.max(...names.map(n => all[n].h)) * S + 6
  const rows = names.reduce((r, n) => r + Math.ceil(all[n].frames.length / PER), 0)
  const W = cw * PER, H = ch * rows
  const px = Buffer.alloc(W * H * 3, 235)
  let row = 0
  for (const n of names) {
    const s = all[n]
    s.frames.forEach((f, fi) => {
      const r = row + Math.floor(fi / PER), c = fi % PER
      for (let X = c * cw; X < (c + 1) * cw; X++) for (let k = 0; k < 3; k++) px[((r * ch) * W + X) * 3 + k] = 160
      for (let Y = r * ch; Y < (r + 1) * ch; Y++) for (let k = 0; k < 3; k++) px[(Y * W + c * cw) * 3 + k] = 160
      for (let i = 0; i < f.length; i++) {
        if (f[i] === '.') continue
        const hex = s.palette[parseInt(f[i], 36)], rgb = [1, 3, 5].map(o => parseInt(hex.slice(o, o + 2), 16))
        const x = i % s.w, y = (i / s.w) | 0
        for (let dy = 0; dy < S; dy++) for (let dx = 0; dx < S; dx++) {
          const X = c * cw + 3 + x * S + dx, Y = r * ch + 3 + y * S + dy
          rgb.forEach((v, k) => (px[(Y * W + X) * 3 + k] = v))
        }
      }
    })
    row += Math.ceil(s.frames.length / PER)
  }
  writePng(file, W, H, px)
}

function gallery(all, file) {
  const html = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clawd 动画一览</title><style>
:root{--bg:#faf9f5;--card:#fff;--ink:#1f1e1d;--sub:#6b6a66;--line:#e6e3da;--used:#3f7d4e}
@media (prefers-color-scheme:dark){:root{--bg:#1f1e1d;--card:#2a2928;--ink:#f0eee6;--sub:#a8a69e;--line:#3a3937;--used:#7cc38b}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,"Microsoft YaHei",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{font-size:20px;margin:0 0 4px}p{color:var(--sub);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;text-align:center}
canvas{image-rendering:pixelated;width:164px;height:150px}.name{font-weight:600}.sub{color:var(--sub);font-size:12px}.used{color:var(--used)}
</style></head><body><main><h1>Clawd 动画一览</h1><p>${Object.keys(all).length} clips from the installed Claude app; green ones are in pet/clawd_sprites.json.</p>
<div class="grid" id="g"></div></main><script>
const D=${JSON.stringify(all)},USED=${JSON.stringify(USED)};const g=document.getElementById('g');const items=[];
for(const n of Object.keys(D)){const s=D[n];const c=document.createElement('div');c.className='card';const cv=document.createElement('canvas');cv.width=44;cv.height=40;c.appendChild(cv);
c.insertAdjacentHTML('beforeend','<div class="name">'+n+'</div><div class="sub">'+s.w+'x'+s.h+' · '+s.frames.length+' frames · '+(USED.includes(n)?'<span class="used">used</span>':'unused')+'</div>');g.appendChild(c);
const ctx=cv.getContext('2d');const imgs=s.frames.map(f=>{const im=ctx.createImageData(s.w,s.h);for(let i=0;i<f.length;i++){if(f[i]==='.')continue;const h=s.palette[parseInt(f[i],36)];im.data[i*4]=parseInt(h.slice(1,3),16);im.data[i*4+1]=parseInt(h.slice(3,5),16);im.data[i*4+2]=parseInt(h.slice(5,7),16);im.data[i*4+3]=255}return im});
items.push({s,ctx,imgs,ox:Math.round(22-s.ax),oy:Math.round(38-s.ay)})}
const t0=performance.now();(function loop(t){for(const it of items){const k=Math.floor((t-t0)/1000*it.s.fps)%it.imgs.length;it.ctx.clearRect(0,0,44,40);it.ctx.putImageData(it.imgs[k],it.ox,it.oy)}requestAnimationFrame(loop)})(t0);
</script></body></html>`
  fs.writeFileSync(file, html)
}

function main() {
  const [cmd, ...args] = process.argv.slice(2)
  const { asar, all } = loadAll()
  if (cmd === 'extract') {
    const missing = USED.filter(n => !all[n])
    if (missing.length) throw new Error('not in this app version: ' + missing.join(', '))
    const out = {}
    for (const n of USED) out[n] = all[n]
    fs.writeFileSync(OUT, JSON.stringify(out))
    console.log(`wrote ${USED.length} clips to ${path.relative(ROOT, OUT)} (${Math.round(fs.statSync(OUT).size / 1024)} KB) from ${asar}`)
  } else if (cmd === 'list') {
    for (const [n, s] of Object.entries(all)) {
      console.log(`${n.padEnd(22)} ${(s.w + 'x' + s.h).padEnd(6)} ${String(s.frames.length).padStart(3)} frames  anchor (${s.ax}, ${s.ay})  ${USED.includes(n) ? 'used' : ''}`)
    }
  } else if (cmd === 'gallery') {
    gallery(all, args[0] || 'gallery.html')
    console.log('wrote', args[0] || 'gallery.html')
  } else if (cmd === 'frames') {
    framesSheet(all, args.slice(1), args[0])
    console.log('wrote', args[0])
  } else if (cmd === 'ids') {
    for (const n of args) {
      const seen = new Map()
      console.log(n.padEnd(22), all[n].frames.map(f => (seen.has(f) || seen.set(f, seen.size), seen.get(f))).join(' '))
    }
  } else {
    console.log(fs.readFileSync(__filename, 'utf8').split('\n').filter(l => l.startsWith('//')).slice(0, 14).join('\n'))
  }
}

main()
