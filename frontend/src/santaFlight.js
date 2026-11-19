import { paintBurst } from './sceneEffects'

const interval = 60
const trailLife = 1.8
const sparkStep = .034
const escapeSpeed = 3.4
const throwSeconds = 2.35
const encoreThrowSeconds = 3.35
const strideFrame = .14
const encoreThrows = [.19, .28, .37, .46, .55, .64, .73, .82]
const giftColors = ['#ff8391', '#a8e5b4', '#9edaff', '#e4afff']
const giftArt = [' //*\\\\ ', '+==|==+', '|##|##|', '|##|##|', '+==|==+']
const font = 'Consolas, monospace'

const sleigh = [
  '         _*',
  '        /__\\',
  '        (o>)',
  '    ___ /##\\_',
  '   /MMM\\/###\\',
  '   \\MM\\=|###|=========',
  '    \\+:::::+/',
  '  ___|___|___/',
]
const rudolph = [
  '          \\|/',
  '           |/_',
  '         _/o_@',
  '  ______/#/',
  '~ /#######/',
  '  \\##|##/',
]
const strides = [
  ['   \\_  /', '     -/'],
  ['   |\\ /\\', '   / /  \\'],
  ['   /   \\_', ' _/      >'],
  ['   /\\  |', '  >  \\_/'],
]

const mirror = { '/': '\\', '\\': '/', '(': ')', ')': '(', '<': '>', '>': '<' }
const columns = 38
const rows = sleigh.length
function spriteCells(lines, offset, firstRow = 0) {
  const cells = []
  for (const [row, line] of lines.entries()) {
    for (const [column, glyph] of Array.from(line).entries()) {
      if (glyph === ' ') continue
      const color = offset
        ? (glyph === '@' ? '#ff646b' : glyph === 'o' ? '#fff0c3' : glyph === '#' ? '#eeb67b' : '#efc998')
        : (glyph === '#' || row < 2 ? '#ff737e' : row === 2 ? '#fff3dc'
            : glyph === 'M' ? '#acdca9' : glyph === ':' ? '#db596a' : '#ffdf94')
      cells.push({ column: offset + column, row: firstRow + row, glyph, color })
    }
  }
  return cells
}
const rudolphColumn = 23
const body = [...spriteCells(sleigh, 0), ...spriteCells(rudolph, rudolphColumn)]
const sprites = strides.map(legs => [...body, ...spriteCells(legs, rudolphColumn, rudolph.length)])

function newFlight() {
  const direction = Math.random() < .5 ? 1 : -1
  const start = .24 + Math.random() * .76
  return {
    direction, start,
    rise: Math.random() < .5 ? 0 : Math.min(start, .2 + Math.random() * .37),
    duration: 7.2 + Math.random() * 1.6,
    sparks: Array.from({ length: 53 }, () => ({
      rise: (Math.random() - .54) * 50,
      drift: 8 + Math.random() * 41,
      height: (Math.random() - .5) * 13,
      glyph: '.+**:+'[Math.floor(Math.random() * 6)],
      color: Math.random() < .72 ? '#ffe6a2' : '#bdefff',
    })),
  }
}

export function createSantaFlight(context) {
  let currentCycle = 0
  let flight
  let drewFrame = false
  let bounds
  let reaction
  let encoreFlight

  function paint(seconds, width, skyHeight, encoreTime = null, reducedMotion = false) {
    const cycle = Math.floor(seconds / interval)
    if (cycle && cycle !== currentCycle) {
      flight = newFlight()
      currentCycle = cycle
      reaction = null
    }
    if (drewFrame) context.clearRect(0, 0, width, skyHeight)
    drewFrame = false
    bounds = null
    const encore = encoreTime !== null
    const activeFlight = encore ? encoreFlight : flight
    const activeReaction = encore ? null : reaction
    const time = encore ? encoreTime - 1.25 : seconds % interval
    if (!activeFlight || time < 0 || time > lastFrameTime(activeFlight, activeReaction, encore) || skyHeight < 100) return
    drewFrame = true
    paintFlight(time, width, skyHeight, activeFlight, activeReaction, encore, reducedMotion)
  }

  function paintFlight(time, width, skyHeight, flight, reaction, encore, reducedMotion) {
    const end = escapeTime(flight, reaction)
    const still = encore && reducedMotion
    const progressAt = time => {
      const boost = reaction ? Math.max(0, time - reaction.time) * (escapeSpeed - 1) : 0
      return (time + boost) / flight.duration
    }
    const size = Math.max(9, Math.min(15, width / 75, skyHeight / 14))
    const stepX = size * .61
    const stepY = size * .89
    const halfWidth = columns * stepX / 2
    const halfHeight = rows * stepY / 2
    const margin = halfWidth + 18
    const skyTop = halfHeight + 12
    const room = skyHeight - skyTop - halfHeight - 24
    const xAt = progress => flight.direction === 1
      ? -margin + progress * (width + margin * 2)
      : width + margin - progress * (width + margin * 2)
    const yAt = time => {
      const base = skyTop + room * (flight.start - flight.rise * progressAt(time))
      if (!reaction || reaction.reducedMotion || time <= reaction.time) return base
      // A quick upward hop as the sleigh accelerates.
      return Math.max(skyTop, base - 20 * (1 - Math.exp(-(time - reaction.time) * 9)))
    }

    const firstSpark = Math.max(0, Math.ceil((time - trailLife) / sparkStep))
    const lastSpark = still ? -1 : Math.floor(Math.min(time, end) / sparkStep)
    context.font = `bold ${Math.max(10, size)}px ${font}`
    for (let index = firstSpark; index <= lastSpark; index += 1) {
      const emission = index * sparkStep
      const age = time - emission
      const spark = flight.sparks[index % flight.sparks.length]
      const fade = 1 - age / trailLife
      context.globalAlpha = fade * (.35 + fade * .65)
      context.fillStyle = context.shadowColor = spark.color
      context.shadowBlur = spark.glyph === '*' ? 16 : 11
      const x = xAt(progressAt(emission)) - flight.direction * (halfWidth + age * spark.drift)
      const y = yAt(emission) + stepY + spark.height + spark.rise * age * .5
      context.fillText(spark.glyph, x, y)
    }

    if (time <= end) {
      const pose = still ? flight.duration / 2 : time
      const x = xAt(progressAt(pose))
      const y = yAt(pose)
      if (!encore && !reaction) bounds = { x, y, halfWidth, halfHeight }
      context.font = `bold ${size}px ${font}`
      context.globalAlpha = 1
      const strideTime = time + (reaction ? Math.max(0, time - reaction.time) * .5 : 0)
      const frame = reducedMotion ? 1 : Math.floor(strideTime / strideFrame) % sprites.length
      for (const cell of sprites[frame]) {
        const backwards = flight.direction === -1
        const glyph = backwards ? mirror[cell.glyph] || cell.glyph : cell.glyph
        const offset = (cell.column + .5) * stepX - halfWidth
        context.fillStyle = context.shadowColor = cell.color
        context.shadowBlur = cell.glyph === '@' ? 16 : 5
        context.fillText(glyph, x + flight.direction * offset, y + (cell.row + .5) * stepY - halfHeight)
      }
    }
    if (reaction?.throwGift) {
      const age = (time - reaction.time) / throwSeconds
      if (age >= 0 && age < 1) {
        const x = xAt(progressAt(reaction.time)) - flight.direction * halfWidth * .52
        const y = yAt(reaction.time)
        drawThrownGift(context, width, skyHeight, x, y, flight.direction, age, reaction.reducedMotion, 0)
      }
    }
    if (encore) {
      for (const [index, position] of encoreThrows.entries()) {
        const emission = position * flight.duration
        const age = (time - emission) / encoreThrowSeconds
        if (age < 0 || age >= 1) continue
        const arrangement = .14 + index * .102
        const x = still ? width * (flight.direction === 1 ? arrangement : 1 - arrangement)
          : xAt(position) - flight.direction * halfWidth * .42
        const y = still ? yAt(flight.duration / 2) + (index % 3) * size * 1.9 : yAt(emission)
        drawThrownGift(context, width, skyHeight, x, y, flight.direction, age, still, index)
      }
    }
    context.globalAlpha = 1
    context.shadowBlur = 0
  }

  return {
    paint,
    startEncore() {
      encoreFlight = { ...newFlight(), start: .62, rise: .25, duration: 6.9 }
    },
    contains(x, y) {
      return !!bounds && !reaction && Math.abs(x - bounds.x) <= bounds.halfWidth &&
        Math.abs(y - bounds.y) <= bounds.halfHeight
    },
    react(seconds, reducedMotion) {
      reaction = { time: seconds % interval, throwGift: Math.random() < .5, reducedMotion }
    },
    isReacting(seconds) {
      return !!reaction && seconds % interval < lastFrameTime(flight, reaction, false)
    },
  }
}

function escapeTime(flight, reaction) {
  return reaction ? reaction.time + (flight.duration - reaction.time) / escapeSpeed : flight.duration
}

function lastFrameTime(flight, reaction, encore) {
  const trailEnd = escapeTime(flight, reaction) + trailLife
  if (encore) return Math.max(trailEnd, flight.duration * encoreThrows.at(-1) + encoreThrowSeconds)
  return reaction?.throwGift ? Math.max(trailEnd, reaction.time + throwSeconds) : trailEnd
}

function drawThrownGift(context, width, skyHeight, x, y, direction, age, reducedMotion, index) {
  const size = Math.min(22, Math.max(12, width / 33), skyHeight / 7)
  const padding = size * 2.4
  const clampX = value => Math.max(padding, Math.min(width - padding, value))
  const drift = Math.min(width * .19, 92 + index % 3 * 22)
  const startX = clampX(x)
  const targetX = clampX(startX - direction * drift)
  const giftX = reducedMotion ? startX : startX + (targetX - startX) * age
  const floor = skyHeight - padding - (index % 3) * size * .38
  const hop = Math.min(36, skyHeight * .1) * Math.sin(Math.PI * Math.min(1, age / .32))
  const giftY = reducedMotion ? y - size * .65 : y + (floor - y) * age ** 1.55 - hop
  const glow = Math.min(1, (1 - age) * 5)
  const color = giftColors[index % giftColors.length]
  context.save()
  context.globalAlpha = glow
  context.shadowBlur = 15
  context.font = `bold ${size}px ${font}`
  for (const [row, line] of giftArt.entries()) {
    const rowY = giftY + (row - 2) * size * .78
    for (const [column, glyph] of Array.from(line).entries()) {
      if (glyph === ' ') continue
      context.fillStyle = context.shadowColor = row === 0 || column === 3 ? '#ffdf9a' : color
      context.fillText(glyph, giftX + (column - 3) * size * .6, rowY)
    }
  }
  context.restore()
  paintBurst(context, giftX, giftY, size * (reducedMotion ? 2.3 : 2.15 + age * .7), glow * .64, '#ffdf99')
}
