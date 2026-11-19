<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { createSantaFlight } from './santaFlight'
import { giftEffect, giftEffectSeconds, paintBurst, paintGiftFlash } from './sceneEffects'
import { encoreSeconds, paintHolidayEncore } from './holidayEncore'
import { createCampfire } from './campfireScene'

const props = defineProps({
  paused: Boolean, reducedMotion: Boolean, skipIntro: Boolean, snowTree: Boolean, terminal: Object,
})
const emit = defineEmits(['light-campfire', 'stoke-campfire'])
const canvas = ref(null)
const treeGiftCanvas = ref(null)
const campfireCanvas = ref(null)
const campfireReady = ref(false)
const field = ref(null)
const encoreCanvas = ref(null)
const santaCanvas = ref(null)
const width = 840
const height = 490
const columns = 120
const rows = 58
const cellWidth = width / columns
const cellHeight = height / rows
const turn = Math.PI * 2
const rotationPeriod = 56
const growthEnd = 1.75
const garlandEnd = 3.25
const ornamentsEnd = 4
const starStart = 4.05
const giftsStart = 4.5
const introEnd = 5.2
const treeFadeSeconds = 1.65
const fireRevealSeconds = .6
const fireFloor = 385
const tilt = .08
const tiltCos = Math.cos(tilt)
const tiltSin = Math.sin(tilt)
const treeText = props.snowTree ? 'SNOW*++..:01' : 'MERRYCHRISTMAS01'
const needles = props.snowTree
  ? ['#577b97', '#799ab5', '#a0bfd4', '#bed6e6', '#e0edf3', '#fbffff']
  : ['#194b39', '#256d4e', '#379360', '#51ab74', '#7acb94', '#c1eccc']
const bark = props.snowTree ? ['#4e6578', '#7893a6', '#adc7d8', '#dbeaf2'] : ['#634736', '#916645', '#bf8b59', '#e4b779']
const garlandLights = props.snowTree ? ['#b2e7ff', '#e8f7ff', '#fff6d6'] : ['#ffd489', '#ffe6ab', '#fff7d6']
const ornaments = props.snowTree ? [
  ['#84b8d5', '#d7edff', '#ffffff'],
  ['#879fca', '#cbdcff', '#f3f9ff'],
  ['#d9b77e', '#ffe6bc', '#fff8e5'],
] : [
  ['#bf4d62', '#ff8b9e', '#ffe3db'],
  ['#4d97bd', '#a5e3ff', '#e6f8ff'],
  ['#be8246', '#f8be72', '#fff2c5'],
]
const snowAccents = props.snowTree ? [
  { angle: 2, colors: ['#bc8e4e', '#ffd17e', '#ffe8b4'] },
  { angle: .49, colors: ['#5d95c5', '#9ed6ff', '#d8f0ff'] },
] : []
const topper = props.snowTree ? '#e7f7ff' : '#ffeaaf'
const pick = items => items[Math.floor(Math.random() * items.length)]
const tree = []
const clamp = value => Math.max(0, Math.min(1, value))
const growAt = y => .14 + clamp((179 - y) / 356) * (growthEnd - .32)

// Sample the branches around four tapered tiers, so each character has a position in 3D.
const tiers = [
  { top: -177, length: 78, radius: 54 },
  { top: -144, length: 104, radius: 90 },
  { top: -92, length: 116, radius: 129 },
  { top: -39, length: 121, radius: 168 },
]
for (const [tier, { top, length, radius }] of tiers.entries()) {
  for (let distance = 0; distance <= length; distance += 3.7) {
    const progress = distance / length
    const spread = radius * (.02 + .98 * progress ** .88 - .05 * progress ** 16)
    const count = Math.max(6, Math.ceil(turn * spread / 4.5))
    for (let index = 0; index < count; index += 1) {
      const angle = (index + (Math.round(distance / 3.7) % 2) * .5) / count * turn
      const radialX = Math.cos(angle)
      const radialZ = Math.sin(angle)
      const branches = Math.cos(7 * angle + tier * .7)
      const y = top + distance + branches * progress * 3
      const edge = spread * (1 + (.07 * branches + .07 * Math.cos(2 * angle)) * progress)
      tree.push({
        x: edge * radialX,
        y,
        z: edge * radialZ,
        radialX,
        radialZ,
        glyph: pick(treeText),
        colors: needles,
        shade: Math.random() * .17 + .045 * Math.max(0, branches),
        revealAt: growAt(y),
      })
    }
  }
}

for (let y = 71; y <= 179; y += 4) {
  const radius = 17 + (y - 71) / 22
  for (let index = 0; index < 24; index += 1) {
    const angle = index / 24 * turn
    const radialX = Math.cos(angle)
    const radialZ = Math.sin(angle)
    tree.push({ x: radius * radialX, y, z: radius * radialZ, radialX, radialZ,
      glyph: index % 4 === 0 ? '#' : '|', colors: bark, shade: .07 * Math.cos(8 * angle),
      revealAt: growAt(y) })
  }
}

// A continuous helix winds from just above the trunk to the crown.
for (let index = 0; index <= 580; index += 1) {
  const progress = index / 580
  const angle = Math.PI / 2 - .37 + progress * turn * 3.65
  const y = 76 - 226 * progress
  const radius = (164 - 143 * progress) * (1 + .055 * Math.cos(2 * angle))
  tree.push({
    x: radius * Math.cos(angle), y, z: radius * Math.sin(angle),
    glyph: index % 9 === 0 ? '*' : pick('+.:'),
    light: pick(garlandLights), phase: progress * turn * 5,
    revealAt: growthEnd + progress * (garlandEnd - growthEnd - .16),
  })
}

const ornamentCount = 25
for (let index = 0; index < ornamentCount + snowAccents.length; index += 1) {
  const tier = tiers[1 + index % 3]
  const accent = snowAccents[index - ornamentCount]
  const angle = accent?.angle ?? index * 2.39996
  const progress = .68 + Math.random() * .22
  const radialX = Math.cos(angle)
  const radialZ = Math.sin(angle)
  const radius = tier.radius * progress ** .88 + 7
  const y = tier.top + tier.length * progress
  const colors = accent?.colors ?? ornaments[index % ornaments.length]
  const revealAt = garlandEnd + Math.min(1, index / ornamentCount) * (ornamentsEnd - garlandEnd - .14)
  for (const [across, vertical, bump, glyph, color] of [
    [0, -6, 3, '+', colors[2]], [-6, 0, 4, 'o', colors[0]], [0, 0, 8, '@', colors[1]],
    [6, 0, 4, 'o', colors[0]], [0, 6, 3, 'o', colors[0]],
  ]) {
    tree.push({
      x: (radius + bump) * radialX - across * radialZ,
      y: y + vertical, z: (radius + bump) * radialZ + across * radialX,
      glyph, light: color, phase: angle, revealAt,
    })
  }
}

// Two intersecting star faces keep the topper visible as it rotates.
const star = Array.from({ length: 10 }, (_, index) => {
  const angle = index * Math.PI / 5 - Math.PI / 2
  const radius = index % 2 === 0 ? 21 : 9
  return [Math.cos(angle) * radius, Math.sin(angle) * radius]
})
for (const [index, [x, y]] of star.entries()) {
  const [nextX, nextY] = star[(index + 1) % star.length]
  for (let step = 0; step < 6; step += 1) {
    const along = step / 6
    const tipX = x + (nextX - x) * along
    const tipY = -207 + y + (nextY - y) * along
    for (const [pointX, pointZ] of [[tipX, 0], [0, tipX]]) {
      tree.push({ x: pointX, y: tipY, z: pointZ, glyph: '+',
        light: topper, phase: 0, revealAt: starStart })
    }
  }
}

// Keep the gifts anchored to the snowy ground while the tree turns.
const gifts = [
  { x: -132, z: 40, size: 42, tall: 44, color: '#f27987', top: '#ff9ca3', side: '#a64257', ribbon: '#ffe0a0' },
  { x: 140, z: 43, size: 49, tall: 44, color: '#7aafd2', top: '#a9d9ed', side: '#4c7497', ribbon: '#f5e9bf' },
  { x: 78, z: 100, size: 40, tall: 34, color: '#c189c5', top: '#e5b4df', side: '#8a568f', ribbon: '#ffe1aa' },
  { x: -77, z: 97, size: 34, tall: 31, color: '#72b88e', top: '#9ed5a9', side: '#438466', ribbon: '#ffdb92' },
]
// The stored gift indices differ from the left-to-right order on screen.
const campfireGiftOrder = [0, 3, 1, 2]
for (const [index, gift] of gifts.entries()) {
  const base = 174
  const half = gift.size / 2
  const top = base - gift.tall
  const revealAt = giftsStart + index * .13
  const slant = index % 2 === 0 ? .38 : -.38
  const sine = Math.sin(slant)
  const cosine = Math.cos(slant)
  const add = (x, y, z, glyph, light, lid = false) => tree.push({
    x: gift.x + x * cosine - z * sine, y, z: gift.z + x * sine + z * cosine,
    glyph, light, revealAt, fixed: true, gift: index, lid,
  })
  for (let x = -half; x <= half; x += 3.5) {
    for (let y = top; y <= base; y += 4) {
      add(x, y, half, Math.abs(x) < 5 ? '|' : '#', Math.abs(x) < 5 ? gift.ribbon : gift.color)
      add(slant > 0 ? half : -half, y, x, Math.abs(x) < 5 ? '|' : ':',
        Math.abs(x) < 5 ? gift.ribbon : gift.side)
    }
    for (let z = -half; z <= half; z += 3.5) {
      add(x, top, z, '+', Math.abs(x) < 5 || Math.abs(z) < 5 ? gift.ribbon : gift.top, true)
    }
  }
  add(-8, top - 6, 0, '<', gift.ribbon, true)
  add(0, top - 9, 0, '*', gift.ribbon, true)
  add(8, top - 6, 0, '>', gift.ribbon, true)
}

const skyStars = [
  [.12, .18, '*'], [.79, .12, '*'], [.28, .40, '+'], [.91, .49, '*'],
  [.19, .72, '+'], [.65, .25, '.'], [.87, .79, '+'], [.06, .54, '.'],
  [.39, .09, '.'], [.72, .57, '+'], [.30, .22, '*'], [.96, .23, '.'],
  [.57, .08, '.'], [.10, .87, '.'], [.82, .33, '.'], [.23, .55, '.'],
  [.47, .19, '.'], [.94, .69, '*'], [.02, .32, '.'], [.38, .83, '.'],
]
const smallStars = Array.from({ length: 33 }, (_, index) => ({
  x: ((index + .35) * .618034) % 1,
  y: .05 + ((index + .65) * .414214) % .86,
  glyph: index % 3 === 0 ? '.' : '+',
}))

const snow = Array.from({ length: 640 }, () => {
  const depth = Math.random()
  return {
    x: Math.random(),
    y: Math.random(),
    speed: 8 + depth * 27,
    opacity: .18 + depth * .48,
    phase: Math.random() * turn,
    drift: 8 + depth * 10,
    font: depth > .8 ? '14px Consolas, monospace' : '10px Consolas, monospace',
    glyph: pick('...+:'),
  }
})

const largeSnow = Array.from({ length: 46 }, () => {
  const depth = Math.random()
  return {
    x: Math.random(),
    y: Math.random(),
    speed: 15 + depth * 18,
    opacity: .46 + depth * .27,
    phase: Math.random() * turn,
    drift: 17 + depth * 17,
    font: `bold ${Math.round(22 + depth * 11)}px Consolas, monospace`,
    glyph: pick('***+'),
  }
})

const fieldGifts = [
  { front: '#9dd5b5', lid: '#cdf5d8', side: '#548971', ribbon: '#f8d891', columns: 9, rows: 4, depth: 4, turn: -1 },
  { front: '#eb8893', lid: '#ffb4ba', side: '#a15363', ribbon: '#ffe2ad', columns: 5, rows: 7, depth: 3, turn: 1 },
  { front: '#a0c7e0', lid: '#d0e7f8', side: '#577e9d', ribbon: '#f5e0ac', columns: 7, rows: 5, depth: 4, turn: -1 },
  { front: '#c5a6d9', lid: '#e4c8ef', side: '#79658f', ribbon: '#ffe0dd', columns: 5, rows: 4, depth: 3, turn: 1 },
  { front: '#d9ae76', lid: '#f6d7a4', side: '#92704b', ribbon: '#edf5e1', columns: 7, rows: 3, depth: 2, turn: 1 },
  { front: '#a5c3a0', lid: '#d8e8bd', side: '#5c7964', ribbon: '#ffe0a8', columns: 5, rows: 6, depth: 4, turn: -1 },
  { front: '#ce8281', lid: '#f0aea4', side: '#854c60', ribbon: '#f5d48d', columns: 8, rows: 3, depth: 4, turn: -1 },
  { front: '#84c5bc', lid: '#b4e5cf', side: '#508889', ribbon: '#f4dcb2', columns: 6, rows: 6, depth: 3, turn: 1 },
  { front: '#8e9ed2', lid: '#c5cdf1', side: '#53628e', ribbon: '#f9dfa2', columns: 5, rows: 4, depth: 5, turn: -1 },
]
const powder = Array.from({ length: 345 }, () => ({
  x: Math.random(),
  depth: Math.random(),
  opacity: .15 + Math.random() * .48,
}))

const ground = Array.from({ length: 155 }, () => {
  const radius = Math.sqrt(Math.random())
  const angle = Math.random() * turn
  return {
    x: width / 2 + Math.cos(angle) * radius * 288,
    y: 421 + Math.sin(angle) * radius * 43,
    glyph: pick('...:+'),
    opacity: .13 + Math.random() * .29,
  }
})

const depths = new Float32Array(columns * rows)
const characters = new Array(depths.length)
let ctx
let treeGiftContext
let campfireContext
let campfireStartedAt = null
let giftStep = 0
let campfire = createCampfire()
let fieldContext
let fieldWidth = 0
let fieldHeight = 0
let terminalBounds
let fieldGiftFloor
let fieldGiftPlacements = []
let snowBanks
let starGlow
let elapsed = props.skipIntro || props.reducedMotion ? introEnd : 0
let flightSeconds = 0
let effectSeconds = 0
let starClickedAt = -Infinity
let encoreStartedAt = null
let encoreContext
const giftAnimations = new Map()
const fieldGiftHits = []
let santaContext
let santa
let santaSkyHeight = 0
let lastFrame
let frame
let observer
let layoutObserver
let visible = false

function projectTree() {
  depths.fill(-Infinity)
  const yaw = .37 + Math.max(0, elapsed - introEnd) * turn / rotationPeriod
  const yawCos = Math.cos(yaw)
  const yawSin = Math.sin(yaw)
  const effects = gifts.map((_, index) => giftEffect(giftAnimations.get(index), effectSeconds, props.reducedMotion))

  for (const point of tree) {
    if (elapsed <= point.revealAt) continue
    const effect = effects[point.gift]
    const x = point.fixed ? point.x + effect.shake * 7 : point.x * yawCos - point.z * yawSin
    const z = point.fixed ? point.z : point.x * yawSin + point.z * yawCos
    const y = point.lid ? point.y - effect.lift * 31 : point.y
    const depth = z * tiltCos - y * tiltSin
    const zoom = 810 / (900 - depth)
    const column = Math.floor((width / 2 + x * zoom) / cellWidth)
    const row = Math.floor((250 + (y * tiltCos + z * tiltSin) * zoom) / cellHeight)
    if (column < 0 || column >= columns || row < 0 || row >= rows) continue
    const index = row * columns + column
    if (depth <= depths[index]) continue
    depths[index] = depth
    characters[index] = point
  }

  for (let index = 0; index < depths.length; index += 1) {
    if (depths[index] === -Infinity) continue
    const point = characters[index]
    const context = point.fixed ? treeGiftContext : ctx
    const reveal = clamp((elapsed - point.revealAt) / .2)
    if (point.light) {
      context.fillStyle = point.light
      context.globalAlpha = reveal * (point.phase === undefined ? 1 : .88 + .12 * Math.cos(elapsed * 1.45 + point.phase))
    } else {
      const normalX = point.radialX * yawCos - point.radialZ * yawSin
      const normalZ = point.radialX * yawSin + point.radialZ * yawCos
      const illumination = .35 + normalZ * .28 - normalX * .30 + point.shade
      const shade = Math.max(0, Math.min(point.colors.length - 1, Math.floor(illumination * point.colors.length)))
      context.fillStyle = reveal < .72 ? '#c9ecda' : point.colors[shade]
      context.globalAlpha = reveal
    }
    context.fillText(point.glyph, (index % columns + .5) * cellWidth, (Math.floor(index / columns) + .5) * cellHeight)
  }
  for (const [index, effect] of effects.entries()) {
    if (!effect.glow) continue
    const { x, z, tall, size } = gifts[index]
    const top = 174 - tall - effect.lift * 11
    const zoom = 810 / (900 - (z * tiltCos - top * tiltSin))
    paintGiftFlash(treeGiftContext, width / 2 + x * zoom, 250 + (top * tiltCos + z * tiltSin) * zoom,
      size * .91, effect, props.reducedMotion)
  }
}

function eraseTree(context, fade) {
  const band = 72
  const edge = (height + band) * fade
  const eraser = context.createLinearGradient(0, edge - band, 0, edge)
  eraser.addColorStop(0, '#000')
  eraser.addColorStop(1, '#0000')
  context.save()
  context.globalCompositeOperation = 'destination-out'
  context.fillStyle = eraser
  context.fillRect(0, 0, width, height)
  context.restore()
}

function paintTree(fade) {
  if (fade === 1 && campfireReady.value) return
  ctx.clearRect(0, 0, width, height)
  treeGiftContext.clearRect(0, 0, width, height)
  if (fade >= 1) return
  treeGiftContext.font = 'bold 10px Consolas, monospace'
  if (elapsed > starStart) {
    ctx.globalAlpha = clamp((elapsed - starStart) / .3)
    ctx.fillStyle = starGlow
    ctx.fillRect(width / 2 - 46, 8, 92, 92)
    ctx.font = 'bold 16px Consolas, monospace'
    ctx.fillStyle = topper
    ctx.fillText('*', width / 2, 60)
  }

  ctx.font = '10px Consolas, monospace'
  ctx.fillStyle = '#90accb'
  for (const cell of ground) {
    ctx.globalAlpha = cell.opacity
    ctx.fillText(cell.glyph, cell.x, cell.y)
  }

  ctx.font = 'bold 10px Consolas, monospace'
  projectTree()
  ctx.globalAlpha = 1
  const flash = clamp(1 - (effectSeconds - starClickedAt) / 1.05)
  if (flash > 0) {
    ctx.save()
    ctx.fillStyle = ctx.shadowColor = props.snowTree ? '#e1f7ff' : '#fff1b2'
    ctx.shadowBlur = 26
    ctx.globalAlpha = flash
    ctx.font = 'bold 29px Consolas, monospace'
    ctx.fillText('*', width / 2, 60)
    ctx.restore()
    paintBurst(ctx, width / 2, 60, props.reducedMotion ? 24 : 15 + (1 - flash) * 50, flash, topper)
  }
  treeGiftContext.globalAlpha = 1
  if (fade > 0) {
    if (props.reducedMotion) {
      for (const context of [ctx, treeGiftContext]) {
        context.save()
        context.globalAlpha = fade
        context.globalCompositeOperation = 'destination-out'
        context.fillStyle = '#000'
        context.fillRect(0, 0, width, height)
        context.restore()
      }
    } else {
      eraseTree(ctx, fade)
      eraseTree(treeGiftContext, fade)
    }
  }
}

function paintField(fade) {
  if (!fieldContext || !fieldWidth || !fieldHeight) return
  fieldContext.clearRect(0, 0, fieldWidth, fieldHeight)
  fieldGiftHits.length = 0
  paintSkyStars()
  paintSnowBanks()
  if (terminalBounds && elapsed > giftsStart && fade < 1) paintFieldGifts(fade)
  const area = fieldWidth * fieldHeight
  paintSnowfall(snow, Math.max(114, Math.round(area / 3350)), '#ccdeed')
  paintSnowfall(largeSnow, Math.max(12, Math.round(area / 47000)), '#e0f2ff')
  fieldContext.globalAlpha = 1
}

function paintSnowfall(flakes, visibleCount, color) {
  fieldContext.fillStyle = color
  const count = Math.min(flakes.length, visibleCount)
  const fallHeight = fieldHeight + 40
  for (let index = 0; index < count; index += 1) {
    const flake = flakes[index]
    fieldContext.font = flake.font
    fieldContext.globalAlpha = flake.opacity
    const x = flake.x * fieldWidth + flake.drift * Math.sin(elapsed * .55 + flake.phase)
    const y = (flake.y * fallHeight + elapsed * flake.speed) % fallHeight - 20
    fieldContext.fillText(flake.glyph, x, y)
  }
}

function paintSkyStars() {
  const skyHeight = snowBanks?.horizon ?? fieldHeight * .6
  const count = Math.min(skyStars.length, Math.max(7, Math.round(fieldWidth / 62)))
  for (let index = 0; index < count; index += 1) {
    const [x, y, glyph] = skyStars[index]
    const bright = glyph === '*'
    const point = glyph === '.'
    const twinkle = Math.sin(elapsed * (.62 + index % 4 * .13) + index * 1.7)
    const px = x * fieldWidth
    const py = y * skyHeight
    fieldContext.fillStyle = bright ? '#fff0be' : '#deedff'
    fieldContext.shadowColor = bright ? '#ffd885b0' : '#badcff80'
    fieldContext.shadowBlur = bright ? 13 : 5
    fieldContext.globalAlpha = (bright ? .85 : point ? .48 : .68) + twinkle * .12
    fieldContext.font = `${bright ? 'bold 23px' : point ? '14px' : '18px'} Consolas, monospace`
    fieldContext.fillText(glyph, px, py)
    if (bright) {
      fieldContext.globalAlpha = .44 + twinkle * .12
      fieldContext.font = '12px Consolas, monospace'
      fieldContext.fillText('.', px - 10, py - 3)
      fieldContext.fillText('.', px + 10, py - 3)
    }
  }
  fieldContext.fillStyle = '#ffdf92'
  fieldContext.shadowColor = '#ffce78aa'
  fieldContext.shadowBlur = 8
  fieldContext.font = 'bold 11px Consolas, monospace'
  const smallCount = Math.min(smallStars.length, Math.max(12, Math.round(fieldWidth / 39)))
  for (let index = 0; index < smallCount; index += 1) {
    const { x, y, glyph } = smallStars[index]
    fieldContext.globalAlpha = .55 + .19 * Math.sin(elapsed * .92 + index * 1.6)
    fieldContext.fillText(glyph, x * fieldWidth, y * skyHeight)
  }
  fieldContext.shadowBlur = 0
  fieldContext.globalAlpha = 1
}

function makeSnowBanks() {
  const horizon = Math.max(32, (terminalBounds?.top ?? fieldHeight * .6) - Math.min(76, fieldWidth * .065))
  const middle = horizon + (fieldHeight - horizon) * .38
  const relief = Math.min(32, fieldWidth * .045)
  const layers = [
    { y: horizon, lift: -relief, colors: ['#789bb64d', '#233c4d89', '#0a131b30'] },
    { y: middle, lift: relief, colors: ['#b1cee224', '#334e6280', '#0a131b66'] },
  ].map(({ y, lift, colors }) => {
    const path = new Path2D()
    path.moveTo(0, y + lift * .12)
    path.bezierCurveTo(fieldWidth * .12, y + lift, fieldWidth * .28, y - lift * .7, fieldWidth * .48, y + lift * .1)
    path.bezierCurveTo(fieldWidth * .68, y + lift * .9, fieldWidth * .88, y - lift * .7, fieldWidth, y - lift * .16)
    path.lineTo(fieldWidth, fieldHeight)
    path.lineTo(0, fieldHeight)
    path.closePath()
    const fill = fieldContext.createLinearGradient(0, y - relief, 0, fieldHeight)
    for (const [index, color] of colors.entries()) fill.addColorStop([0, .33, 1][index], color)
    return { path, fill }
  })
  return { horizon, relief, layers }
}

function paintSnowBanks() {
  if (!snowBanks) return
  const { horizon, relief, layers } = snowBanks
  for (const { path, fill } of layers) {
    fieldContext.fillStyle = fill
    fieldContext.fill(path)
  }
  fieldContext.fillStyle = '#d9e9f4'
  const count = Math.min(powder.length, Math.round(fieldWidth * .28))
  for (let index = 0; index < count; index += 1) {
    const flake = powder[index]
    const y = horizon + relief * .45 + flake.depth * (fieldHeight - horizon - relief * .45)
    fieldContext.globalAlpha = flake.opacity * (.32 + flake.depth * .68)
    fieldContext.fillRect(flake.x * fieldWidth, y, .8 + flake.depth * 2.8, 1 + flake.depth * .6)
  }
  fieldContext.globalAlpha = 1
}

function layoutFieldGifts() {
  if (!terminalBounds) return []
  const { left, top, right } = terminalBounds
  const sideSpace = Math.min(left, fieldWidth - right)
  let placements
  if (sideSpace >= 105) {
    const size = Math.min(16, sideSpace / 12)
    const floor = Math.max(top + 100, fieldGiftFloor)
    const depth = Math.min(205, sideSpace * .28)
    placements = [
      [left * .24, floor - 44, size * .8, 5], [right + sideSpace * .83, floor - 42, size * .76, 4],
      [left * .73, floor - 26, size * .69, 3], [right + sideSpace * .25, floor - 25, size * .9, 1],
      [left * .43, floor - 6, size, 0], [right + sideSpace * .60, floor - 4, size, 2],
    ]
    if (sideSpace >= 240) {
      placements.push(
        [left * .15, floor - depth * .77, size * .65, 8], [right + sideSpace * .92, floor - depth * .79, size * .63, 5],
        [left * .86, floor - depth * .67, size * .69, 6], [right + sideSpace * .19, floor - depth * .71, size * .67, 7],
      )
    }
    if (sideSpace >= 475) {
      placements.push(
        [left * .34, floor - depth * .97, size * .78, 1], [right + sideSpace * .14, floor - depth * .96, size * .76, 0],
        [left * .67, floor - depth * 1.42, size * .66, 8], [right + sideSpace * .49, floor - depth * 1.43, size * .70, 3],
        [left * .54, floor - depth * .64, size * .92, 7], [right + sideSpace * .69, floor - depth * .93, size * .79, 6],
      )
      if (floor - top >= 475) {
        placements.push(
          [fieldWidth * .468, floor - 5, 9, 4], [fieldWidth * .53, floor - 2, 8, 8],
        )
      }
    }
  } else {
    const edge = Math.max(29, fieldWidth * .07)
    const size = Math.min(11, fieldWidth / 55)
    placements = [
      [edge + size * 3.7, top - 23, size * .71, 3], [fieldWidth - edge - size * 3.7, top - 23, size * .7, 4],
      [edge, top - 8, size, 0], [fieldWidth - edge, top - 8, size, 1],
    ]
  }
  return placements.map(([x, floor, size, shape], id) => ({ x, floor, size, shape, id }))
    .sort((a, b) => a.floor - b.floor)
}

function paintFieldGifts(fade) {
  for (const [index, { x, floor, size, shape, id }] of fieldGiftPlacements.entries()) {
    const delay = .13 + index / fieldGiftPlacements.length * .37
    const fadeAt = .5 + .24 * clamp(floor / fieldHeight)
    const remaining = props.reducedMotion ? 1 - fade : 1 - clamp((fade - fadeAt) / .26)
    const opacity = clamp((elapsed - giftsStart - delay) / .2) * remaining
    if (opacity > 0) paintGiftBox(x, floor, size, fieldGifts[shape], opacity, gifts.length + id)
  }
}

function paintGiftBox(x, floor, size, gift, opacity, id) {
  const context = fieldContext
  const faceWidth = size * .62 * gift.columns
  const boxHeight = size * .84 * gift.rows
  const sideWidth = size * .5 * gift.depth
  const depthX = sideWidth * gift.turn
  const rise = size * .33 * gift.depth
  const restX = x
  const effect = giftEffect(giftAnimations.get(id), effectSeconds, props.reducedMotion)
  const { shake, lift } = effect
  x += shake * size * .55
  const edgeX = x - (faceWidth + sideWidth) / 2 - Math.min(0, depthX)
  const sideX = edgeX + (depthX > 0 ? faceWidth : 0)
  const edgeY = floor - boxHeight
  const lidRise = lift * size * 2.8
  const halfWidth = (faceWidth + sideWidth) / 2 + 4
  fieldGiftHits.push({ id, left: restX - halfWidth, right: restX + halfWidth,
    top: edgeY - rise - size * 1.3, bottom: floor + 4 })

  context.globalAlpha = opacity * .5
  context.fillStyle = '#07121d'
  context.beginPath()
  context.ellipse(restX, floor + size * .15, (faceWidth + sideWidth) * .57, size * .42, 0, 0, turn)
  context.fill()

  // Draw the three visible planes with the same projection for their edges and glyphs.
  const faces = [
    { x: edgeX, y: edgeY - lidRise, dx: faceWidth, dy: 0, rx: depthX, ry: -rise, cols: gift.columns, rows: gift.depth, color: gift.lid, lid: true, glyph: '+' },
    { x: sideX, y: edgeY, dx: depthX, dy: -rise, rx: 0, ry: boxHeight, cols: gift.depth, rows: gift.rows, color: gift.side, glyph: ':' },
    { x: edgeX, y: edgeY, dx: faceWidth, dy: 0, rx: 0, ry: boxHeight, cols: gift.columns, rows: gift.rows, color: gift.front, glyph: '+' },
  ]
  context.font = `bold ${size}px Consolas, monospace`
  for (const face of faces) {
    const { x, y, dx, dy, rx, ry, cols, rows, color, lid, glyph } = face
    context.fillStyle = color
    context.globalAlpha = opacity * .13
    context.beginPath()
    context.moveTo(x, y)
    context.lineTo(x + dx, y + dy)
    context.lineTo(x + dx + rx, y + dy + ry)
    context.lineTo(x + rx, y + ry)
    context.closePath()
    context.fill()
    context.globalAlpha = opacity
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < cols; column += 1) {
        const ribbon = column === Math.floor(cols / 2) || lid && row === Math.floor(rows / 2)
        const u = (column + .5) / cols
        const v = (row + .5) / rows
        context.fillStyle = ribbon ? gift.ribbon : color
        context.fillText(ribbon ? (lid ? '=' : '|') : glyph, x + dx * u + rx * v, y + dy * u + ry * v)
      }
    }
  }
  context.fillStyle = gift.ribbon
  context.fillText('.-. .-.', x, edgeY - rise * .5 - size * 1.15 - lidRise)
  context.fillText('(<*>)', x, edgeY - rise * .5 - size * .4 - lidRise)
  paintGiftFlash(context, x, edgeY - rise * .4 - lidRise * .32,
    Math.max(19, (faceWidth + sideWidth) * .51), effect, props.reducedMotion)
}

function paint() {
  const campfireTime = campfireStartedAt === null ? 0 : effectSeconds - campfireStartedAt
  const fade = clamp(campfireTime / treeFadeSeconds)
  paintField(fade)
  paintTree(fade)
  if (campfireStartedAt !== null) {
    campfireContext.clearRect(0, 0, width, height)
    const reveal = clamp((campfireTime - treeFadeSeconds) / fireRevealSeconds)
    if (reveal > 0) {
      campfireReady.value = true
      campfire.paint(campfireContext, width / 2, fireFloor, elapsed, effectSeconds, reveal, props.reducedMotion)
    }
    return
  }
  let encoreTime = null
  if (encoreStartedAt !== null) {
    const age = effectSeconds - encoreStartedAt
    if (age >= encoreSeconds) encoreStartedAt = null
    else encoreTime = age
    paintHolidayEncore(encoreContext, fieldWidth, fieldHeight, santaSkyHeight, encoreTime, props.reducedMotion)
  }
  santa?.paint(flightSeconds, fieldWidth, santaSkyHeight, encoreTime, props.reducedMotion)
}

function sceneTarget(event) {
  const fieldRect = field.value.getBoundingClientRect()
  const rect = canvas.value.getBoundingClientRect()
  const x = (event.clientX - rect.left) * width / rect.width
  const y = (event.clientY - rect.top) * height / rect.height
  if (campfireStartedAt !== null) {
    return campfireReady.value && campfire.contains(x, y, width / 2, fireFloor) ? 'fire' : null
  }
  const fieldX = event.clientX - fieldRect.left
  const fieldY = event.clientY - fieldRect.top
  if (santa?.contains(fieldX, fieldY)) return 'santa'
  const box = fieldGiftHits.findLast(({ left, right, top, bottom }) =>
    fieldX >= left && fieldX <= right && fieldY >= top && fieldY <= bottom)
  if (box) return box.id

  const column = Math.floor(x / cellWidth)
  const row = Math.floor(y / cellHeight)
  if (row < 0 || row >= rows || column < 0 || column >= columns) return null

  let hit = null
  for (const [dx, dy] of [[0, 0], [-1, 0], [1, 0], [0, -1], [0, 1]]) {
    const col = column + dx
    const line = row + dy
    if (col < 0 || col >= columns || line < 0 || line >= rows) continue
    const index = line * columns + col
    if (depths[index] === -Infinity) continue
    const gift = characters[index].gift
    if (gift !== undefined) return gift
    hit = 'tree'
  }
  return hit
}

function lightStar() {
  if (campfireStartedAt !== null || elapsed <= starStart) return
  starClickedAt = effectSeconds
  if (encoreContext && encoreStartedAt === null && Math.random() < .01) {
    encoreStartedAt = effectSeconds
    santa?.startEncore()
  }
  playReaction()
}

function unlockCampfire(target) {
  giftStep = target === campfireGiftOrder[giftStep] ? giftStep + 1 : 0
  if (giftStep !== campfireGiftOrder.length || !campfireContext) return false

  campfireStartedAt = effectSeconds
  giftAnimations.clear()
  encoreStartedAt = null
  encoreContext?.clearRect(0, 0, fieldWidth, fieldHeight)
  santaContext?.clearRect(0, 0, fieldWidth, santaSkyHeight)
  emit('light-campfire', treeFadeSeconds)
  return true
}

function stokeCampfire() {
  campfire.stoke(effectSeconds)
  emit('stoke-campfire')
  playReaction()
}

function returnToTree() {
  if (!campfireReady.value) return
  campfireReady.value = false
  campfireStartedAt = null
  campfire = createCampfire()
  giftStep = 0
  starClickedAt = -Infinity
  campfireContext.clearRect(0, 0, width, height)
  playReaction()
  canvas.value.focus({ preventScroll: true })
}

defineExpose({ campfireReady, returnToTree })

function activateScene() {
  if (campfireReady.value) stokeCampfire()
  else lightStar()
}

function interact(event) {
  const target = sceneTarget(event)
  if (target === 'fire') stokeCampfire()
  else if (target === 'tree') lightStar()
  else if (target === 'santa') {
    santa.react(flightSeconds, props.reducedMotion)
    playReaction()
  }
  else if (target !== null) {
    if (!unlockCampfire(target) && !giftAnimations.has(target)) {
      giftAnimations.set(target, { start: effectSeconds, open: Math.random() < .2 })
    }
    playReaction()
  }
}

function playReaction() {
  if (props.paused && frame === undefined) syncAnimation()
  paint()
}

function sizeCanvas(element, context, layoutWidth, layoutHeight, logicalWidth, logicalHeight) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  const pixelWidth = Math.max(1, Math.round(layoutWidth * ratio))
  const pixelHeight = Math.max(1, Math.round(layoutHeight * ratio))
  if (element.width !== pixelWidth || element.height !== pixelHeight) {
    element.width = pixelWidth
    element.height = pixelHeight
  }
  context.setTransform(pixelWidth / logicalWidth, 0, 0, pixelHeight / logicalHeight, 0, 0)
  context.textAlign = 'center'
  context.textBaseline = 'middle'
}

function resizeScene() {
  if (!ctx || !fieldContext) return
  const treeRect = canvas.value.getBoundingClientRect()
  const fieldRect = field.value.getBoundingClientRect()
  if (!treeRect.width || !fieldRect.width || !fieldRect.height) return
  fieldWidth = fieldRect.width
  fieldHeight = fieldRect.height
  fieldGiftFloor = document.documentElement.clientHeight - fieldRect.top - window.scrollY - 34
  const panel = props.terminal?.getBoundingClientRect()
  terminalBounds = panel && {
    left: panel.left - fieldRect.left, right: panel.right - fieldRect.left,
    top: panel.top - fieldRect.top,
  }
  fieldGiftPlacements = layoutFieldGifts()
  sizeCanvas(canvas.value, ctx, treeRect.width, treeRect.height, width, height)
  sizeCanvas(treeGiftCanvas.value, treeGiftContext, treeRect.width, treeRect.height, width, height)
  if (campfireContext) sizeCanvas(campfireCanvas.value, campfireContext, treeRect.width, treeRect.height, width, height)
  sizeCanvas(field.value, fieldContext, fieldWidth, fieldHeight, fieldWidth, fieldHeight)
  if (encoreContext) sizeCanvas(encoreCanvas.value, encoreContext, fieldWidth, fieldHeight, fieldWidth, fieldHeight)
  snowBanks = makeSnowBanks()
  // The lowest flight stays above even the highest edge of the snow bank.
  santaSkyHeight = Math.max(1, snowBanks.horizon - snowBanks.relief)
  if (santaContext) {
    santaCanvas.value.style.height = `${santaSkyHeight}px`
    sizeCanvas(santaCanvas.value, santaContext, fieldWidth, santaSkyHeight, fieldWidth, santaSkyHeight)
  }
  starGlow = ctx.createRadialGradient(width / 2, 60, 0, width / 2, 60, 46)
  starGlow.addColorStop(0, props.snowTree ? '#bceaff77' : '#f8d4836c')
  starGlow.addColorStop(.4, props.snowTree ? '#bceaff24' : '#f8d48323')
  starGlow.addColorStop(1, props.snowTree ? '#bceaff00' : '#f8d48300')
  paint()
}

function animate(now) {
  frame = undefined
  lastFrame ??= now
  if (now - lastFrame >= 32) {
    const delta = now - lastFrame
    const step = Math.min(delta, 80) / 1000
    if (!props.paused) {
      elapsed += step
      flightSeconds += delta / 1000
    } else if (santa?.isReacting(flightSeconds)) flightSeconds += step
    effectSeconds += step
    for (const [id, effect] of giftAnimations) {
      if (effectSeconds - effect.start >= (effect.open ? giftEffectSeconds : .55)) giftAnimations.delete(id)
    }
    lastFrame = now
    paint()
  }
  if (shouldAnimate()) frame = requestAnimationFrame(animate)
}

function shouldAnimate() {
  return visible && !document.hidden &&
    (!props.paused || encoreStartedAt !== null || giftAnimations.size ||
      effectSeconds - starClickedAt < 1.05 || santa?.isReacting(flightSeconds) ||
      (campfireStartedAt !== null && (effectSeconds - campfireStartedAt <= treeFadeSeconds + fireRevealSeconds ||
        campfire.isReacting(effectSeconds))))
}

function syncAnimation() {
  cancelAnimationFrame(frame)
  frame = undefined
  lastFrame = undefined
  if (shouldAnimate()) frame = requestAnimationFrame(animate)
}

onMounted(() => {
  ctx = canvas.value.getContext('2d')
  treeGiftContext = treeGiftCanvas.value.getContext('2d')
  campfireContext = campfireCanvas.value.getContext('2d')
  fieldContext = field.value.getContext('2d')
  if (!ctx || !treeGiftContext || !fieldContext) return
  encoreContext = encoreCanvas.value.getContext('2d')
  santaContext = santaCanvas.value.getContext('2d')
  if (santaContext) santa = createSantaFlight(santaContext)
  resizeScene()
  layoutObserver = new ResizeObserver(resizeScene)
  layoutObserver.observe(canvas.value)
  layoutObserver.observe(field.value)
  if (props.terminal) layoutObserver.observe(props.terminal)

  observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    syncAnimation()
  })
  observer.observe(field.value)
  document.addEventListener('visibilitychange', syncAnimation)
})

watch(() => props.paused, syncAnimation)
watch(() => props.terminal, (terminal, previous) => {
  if (!layoutObserver) return
  if (previous) layoutObserver.unobserve(previous)
  if (terminal) layoutObserver.observe(terminal)
  resizeScene()
}, { flush: 'post' })
watch(() => props.reducedMotion, reduced => {
  if (reduced && elapsed < introEnd) {
    elapsed = introEnd
    if (ctx) paint()
  }
})
onUnmounted(() => {
  cancelAnimationFrame(frame)
  observer?.disconnect()
  layoutObserver?.disconnect()
  document.removeEventListener('visibilitychange', syncAnimation)
})
</script>

<template>
  <div class="winter-backdrop" @click="interact"
    @pointermove="$event.currentTarget.style.cursor = sceneTarget($event) === null ? '' : 'pointer'">
    <canvas ref="field" class="winter-field" aria-hidden="true" />
    <canvas ref="canvas" class="ascii-tree" :class="{ 'snow-tree': snowTree }" width="840" height="490"
      role="button" tabindex="0"
      :aria-label="campfireReady ? '모닥불에 불 지피기' : snowTree ? 'ASCII 눈꽃 트리의 별 밝히기' : 'ASCII 크리스마스트리의 별 밝히기'"
      @keydown.enter.prevent="activateScene" @keydown.space.prevent="activateScene" />
    <canvas ref="treeGiftCanvas" class="tree-gifts" width="840" height="490" aria-hidden="true" />
    <canvas ref="campfireCanvas" class="campfire-scene" width="840" height="490" aria-hidden="true" />
    <canvas ref="encoreCanvas" class="holiday-encore" aria-hidden="true" />
    <canvas ref="santaCanvas" class="santa-sky" aria-hidden="true" />
  </div>
</template>
