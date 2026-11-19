import { paintCampfireGuests } from './campfireGuests'

const font = 'Consolas, monospace'
const tones = ['#a64f28', '#d3682d', '#ee8737', '#ffac4d', '#ffce6e', '#ffebaa', '#fff4cf']
const flameGlyphs = '.:;*+x#%'
const mainFlames = [
  { x: -50, width: 29, height: 109, bend: 16, phase: .7 },
  { x: -23, width: 36, height: 166, bend: 1, phase: 1.7 },
  { x: 1, width: 43, height: 213, bend: -12, phase: 3.5 },
  { x: 25, width: 32, height: 173, bend: -1, phase: 2.4 },
  { x: 52, width: 30, height: 109, bend: -17, phase: 4.2 },
]
const logFlames = [
  { x: -43, width: 9, height: 65, bend: 14, phase: 2.2 },
  { x: 30, width: 11, height: 86, bend: -10, phase: 4.6 },
]

const backLogs = [
  { foot: [86, -8], tip: [-20, -108], radius: 9, warm: false },
  { foot: [76, -39], tip: [-48, -87], radius: 8, warm: false },
]
const frontLogs = [
  { foot: [-99, 3], tip: [-19, -85], radius: 12, warm: false },
  { foot: [83, 5], tip: [9, -90], radius: 10, warm: false },
  { foot: [-50, 16], tip: [-2, -64], radius: 13, warm: true },
]
const centerLog = { foot: [43, 14], tip: [-9, -127], radius: 14, warm: true }
const clamp = value => Math.max(0, Math.min(1, value))
const guestSeconds = 15
const flareSeconds = 1.8
const stoneCount = 15
const stones = Array.from({ length: stoneCount }, (_, index) => {
  const angle = (index + .2) * Math.PI * 2 / stoneCount
  return {
    x: Math.cos(angle) * 115,
    y: Math.sin(angle) * 23,
    width: 32 + index * 7 % 12,
    height: 15 + index * 5 % 9,
    grain: index * 13 % 7,
  }
}).sort((a, b) => a.y - b.y)
const embers = Array.from({ length: 15 }, (_, index) => ({
  x: Math.sin(index * 17) * (11 + index % 6 * 6),
  drift: Math.cos(index * 31) * (7 + index % 5 * 4),
  rise: 51 + index % 9 * 12,
  phase: (index * .618) % 1,
  glyph: '..:+'[index % 4],
}))

function paintGlow(context, x, y, light, flare) {
  context.save()
  context.translate(x, y - 15)
  context.scale(1, .27)
  const radius = 180 + flare * 13
  const halo = context.createRadialGradient(0, 0, 3, 0, 0, radius)
  halo.addColorStop(0, '#ffaa6173')
  halo.addColorStop(.28, '#ec783d4a')
  halo.addColorStop(.68, '#a443222c')
  halo.addColorStop(1, '#a4432200')
  context.globalAlpha *= light
  context.fillStyle = halo
  context.fillRect(-radius, -radius, radius * 2, radius * 2)
  context.restore()

  const aura = context.createRadialGradient(x, y - 63, 4, x, y - 63, 138 + flare * 13)
  aura.addColorStop(0, '#df552239')
  aura.addColorStop(.54, '#ee79301c')
  aura.addColorStop(1, '#ee793000')
  context.fillStyle = aura
  context.fillRect(x - 200, y - 280, 400, 400)
}

function paintFlames(context, x, y, time, flare, opacity, flames) {
  const stepX = 6
  const stepY = 7
  const layers = flames.map(tongue => ({
    ...tongue,
    liveHeight: tongue.height + Math.sin(time * 1.31 + tongue.phase) * 5 + flare * 16,
    lean: Math.sin(time * 1.1 + tongue.phase) * 9,
  }))
  const topRow = Math.ceil(Math.max(...layers.map(layer => layer.liveHeight)) / stepY)
  context.font = 'bold 11px ' + font
  for (let row = 0; row < topRow; row += 1) {
    const up = row * stepY
    const tonguesAtRow = layers.flatMap(tongue => {
      const rise = up / tongue.liveHeight
      if (rise >= 1) return []
      const wave = time * (3.3 + .16 * tongue.phase) - up * .062 + tongue.phase
      const curl = Math.sin(wave) * rise * 13
      const curve = Math.sin(rise * 7.3 + tongue.phase) * rise * 9
      return [{
        center: tongue.x * (1 - rise * .65) + (tongue.bend + tongue.lean) * rise ** 1.3 + curve + curl,
        span: tongue.width * (1 - rise) ** .65 * (1 + Math.sin(wave + 1.3) * rise * .38),
        intensity: (1 - rise * .66) * (.91 + Math.cos(wave) * rise * .21),
      }]
    })
    for (let column = -15; column <= 15; column += 1) {
      const across = column * stepX
      let heat = 0
      for (const tongue of tonguesAtRow) {
        const edge = 1 - Math.abs(across - tongue.center) / tongue.span
        heat = Math.max(heat, edge * tongue.intensity)
      }
      if (heat <= .025) continue
      const grain = Math.sin(column * 2.7 + row * 2.1) * .075
      const current = Math.sin(time * 4 - up * .068 + across * .09) * .5 + .5
      const flicker = current ** 2 * Math.min(1, up / 28)
      const hot = clamp(heat * 1.13 + grain + flicker * .12)
      const shade = Math.min(tones.length - 1, Math.floor(hot * tones.length))
      const glyph = flameGlyphs[Math.min(flameGlyphs.length - 1, Math.floor(hot * flameGlyphs.length))]
      context.globalAlpha = opacity * clamp(heat * 2.8) * clamp(.68 + flicker * .25 + flare * .12)
      context.fillStyle = tones[shade]
      context.fillText(glyph, x + across, y - up)
    }
  }
  context.globalAlpha = opacity
}

function paintEmbers(context, x, y, time, age, opacity, reduced) {
  context.font = 'bold 10px ' + font
  for (const [index, ember] of embers.entries()) {
    const burst = index >= 9
    if ((burst && age > 1.3) || (reduced && index % 3)) continue
    const progress = burst ? clamp(age * (.62 + ember.phase * .45)) : (time * .19 + ember.phase) % 1
    const lift = ember.rise * progress
    const drift = ember.drift * progress
    const visible = Math.sin(progress * Math.PI) * (burst ? .85 : .50)
    context.globalAlpha = opacity * visible
    context.fillStyle = context.shadowColor = tones[2 + index % 4]
    context.shadowBlur = 6
    context.fillText(ember.glyph, x + ember.x + drift, y - (burst ? 70 : 153) - lift)
  }
  context.shadowBlur = 0
  context.globalAlpha = opacity
}

function paintLog(context, x, y, { foot, tip, radius, warm }) {
  const dx = tip[0] - foot[0]
  const dy = tip[1] - foot[1]
  const length = Math.hypot(dx, dy)
  context.save()
  context.translate(x + foot[0], y + foot[1])
  context.rotate(Math.atan2(dy, dx))

  const bark = context.createLinearGradient(0, -radius, 0, radius)
  bark.addColorStop(0, '#322420')
  bark.addColorStop(.26, warm ? '#896048' : '#674330')
  bark.addColorStop(.6, warm ? '#5d3d2c' : '#503329')
  bark.addColorStop(1, '#241b1b')
  context.fillStyle = bark
  context.beginPath()
  context.moveTo(0, -radius * .95)
  context.lineTo(length * .66, -radius)
  context.lineTo(length - 2, -radius * .75)
  context.lineTo(length + 5, -radius * .24)
  context.lineTo(length, radius * .8)
  context.lineTo(length * .37, radius * .86)
  context.lineTo(0, radius)
  context.closePath()
  context.fill()

  context.font = 'bold 9px ' + font
  for (let across = -radius + 3; across < radius - 1; across += 4) {
    context.fillStyle = across < 0 ? (warm ? '#bd8a64' : '#a2704a') : '#744a34'
    for (let along = 8; along < length - 3; along += 7) {
      const grain = Math.floor(along * .71 + across * 2.8 + radius) & 7
      context.fillText('=-.:=~_:'[grain], along, across)
    }
  }
  context.fillStyle = warm ? '#9a6b48' : '#79563e'
  context.beginPath()
  context.ellipse(0, 0, radius * .57, radius * .94, 0, 0, Math.PI * 2)
  context.fill()
  context.fillStyle = '#4d3427'
  context.font = 'bold 11px ' + font
  context.fillText('()', 0, 0)
  context.restore()
}

function paintStones(context, x, y, foreground) {
  context.font = 'bold 10px ' + font
  for (const stone of stones) {
    if ((stone.y >= 0) !== foreground) continue
    const left = x + stone.x - stone.width / 2
    const right = left + stone.width
    const floor = y + stone.y + 4
    const top = floor - stone.height
    const shade = context.createLinearGradient(0, top, 0, floor)
    shade.addColorStop(0, foreground ? '#897364' : '#675b54')
    shade.addColorStop(.45, foreground ? '#60534d' : '#554744')
    shade.addColorStop(1, '#252428')
    context.fillStyle = shade
    context.beginPath()
    context.moveTo(left, floor - stone.height * .34)
    context.quadraticCurveTo(left + 1, top + 1, left + stone.width * .31, top)
    context.quadraticCurveTo(right - 2, top - 2, right, floor - stone.height * .44)
    context.quadraticCurveTo(right + 1, floor + 1, left + stone.width * .46, floor)
    context.quadraticCurveTo(left, floor - 1, left, floor - stone.height * .34)
    context.fill()
    context.fillStyle = foreground ? '#ad9582' : '#947b68'
    context.fillText(['.::', ':..', ':.='][stone.grain % 3], left + stone.width * .48, top + 5)
  }
}

function paintCoal(context, x, y, time, flare, opacity) {
  const bed = context.createRadialGradient(x, y, 0, x, y, 106)
  bed.addColorStop(0, '#70341e')
  bed.addColorStop(.52, '#493024')
  bed.addColorStop(1, '#1f1b2000')
  context.fillStyle = bed
  context.beginPath()
  context.ellipse(x, y + 3, 111, 26, 0, 0, Math.PI * 2)
  context.fill()
  context.font = 'bold 10px ' + font
  for (let i = 0; i < 37; i += 1) {
    const dx = Math.sin(i * 28.6) * (20 + i * 7 % 71)
    const dy = Math.cos(i * 7.7) * (4 + i * 3 % 15)
    const light = .47 + Math.sin(time * 1.45 + i * 2.1) * .17
    context.globalAlpha = opacity * clamp(light + flare * .46)
    context.fillStyle = tones[1 + i % 4]
    context.fillText('.:*+'[i % 4], x + dx, y + dy)
  }
  context.globalAlpha = opacity
}

function flareAt(age, initial) {
  const progress = clamp(age / .33)
  const rise = progress * progress * (3 - 2 * progress)
  const decay = clamp((age - .33) / (flareSeconds - .33))
  return (initial + (1 - initial) * rise) * (1 - decay * decay * (3 - 2 * decay))
}

export function createCampfire() {
  let stokedAt = -Infinity
  let initialFlare = 0
  let guestsStartedAt = -Infinity
  let guestsUntil = -Infinity

  return {
    stoke(seconds) {
      initialFlare = flareAt(seconds - stokedAt, initialFlare)
      stokedAt = seconds
      if (Math.random() < .10) {
        if (seconds >= guestsUntil) guestsStartedAt = seconds
        guestsUntil = seconds + guestSeconds
      }
    },
    isReacting(seconds) {
      return seconds - stokedAt < flareSeconds || seconds < guestsUntil
    },
    contains(x, y, center, floor) {
      return Math.abs(x - center) <= 127 && y >= floor - 245 && y <= floor + 40
    },
    paint(context, x, y, time, seconds, opacity, reduced) {
      const age = seconds - stokedAt
      const flare = flareAt(age, initialFlare)
      const flicker = reduced ? 0 : time
      context.save()
      context.globalAlpha = opacity
      paintGlow(context, x, y, .75 + Math.sin(flicker * 1.6) * .035 + flare * .17, flare)
      paintStones(context, x, y, false)
      paintCoal(context, x, y, flicker, flare, opacity)
      for (const log of backLogs) paintLog(context, x, y, log)
      const lift = reduced ? flare * .25 : flare
      paintFlames(context, x, y - 5, flicker, lift, opacity, mainFlames)
      for (const log of frontLogs) paintLog(context, x, y, log)
      paintFlames(context, x, y - 8, flicker, lift, opacity * (.64 + flare * .26), logFlames)
      context.globalAlpha = opacity
      paintLog(context, x, y, centerLog)
      paintEmbers(context, x, y, flicker, age, opacity, reduced)
      paintStones(context, x, y, true)
      if (seconds < guestsUntil) {
        const time = seconds - guestsStartedAt
        const fade = clamp(time / .5) * clamp((guestsUntil - seconds) / .95)
        paintCampfireGuests(context, x, y, time, fade * opacity, reduced)
      }
      context.restore()
    },
  }
}
