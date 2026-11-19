export const encoreSeconds = 11.3

const clamp = value => Math.max(0, Math.min(1, value))
const ease = value => 1 - (1 - clamp(value)) ** 3
const ornaments = [
  { x: .13, length: .68, color: '#ffc968', art: ['  +  ', ' /|\\ ', '<+*+>', " \\|/ ", '  +  '] },
  { x: .17, length: .38, color: '#ff8696', art: [' _|_ ', ' /o\\ ', '(o*o)', "(ooo)", " '-' "] },
  { x: .24, length: .53, color: '#ffda83', art: [' _|_ ', ' /+\\ ', '/+++\\', "'-o-'"] },
  { x: .31, length: .25, color: '#ff8291', stripe: '#fff1d5', art: [' .--. ', '/=/\\| ', "'-'|/ ", '   /= ', '   |/ '] },
  { x: .38, length: .13, color: '#a6e7ff', art: [' _|_ ', ' /+\\ ', '(+*+)', "(+++)", " '-' "] },
]
const curtainFolds = ['#642638', '#944153', '#c76c79', '#a74d62', '#773246']

export function paintHolidayEncore(context, width, height, skyHeight, seconds, reducedMotion) {
  context.clearRect(0, 0, width, height)
  if (seconds === null) return
  const fade = clamp((encoreSeconds - seconds) / 1.4)
  const beam = ease(seconds / 1.25)
  const reach = Math.min(height, skyHeight + 78)
  drawBeam(context, width, reach, reducedMotion ? 1 : beam, beam * fade)

  const drop = ease((seconds - .18) / 1.5)
  const curtainWidth = Math.min(width * .295, 445)
  const curtainHeight = Math.min(skyHeight * .94, 535)
  for (const direction of [1, -1]) {
    if (drop > 0) drawCurtain(context, width, curtainWidth, curtainHeight, direction, drop, fade, seconds, reducedMotion)
  }
  drawGarland(context, width, seconds, fade, reducedMotion)
  for (const direction of [1, -1]) drawOrnaments(context, width, curtainHeight * .79, direction, seconds, fade, reducedMotion)
}

function drawBeam(context, width, height, reach, glow) {
  context.save()
  context.translate(width / 2, 0)
  context.scale(Math.min(width * .36, 440), Math.max(1, height * reach))
  const light = context.createRadialGradient(0, 0, .02, 0, .14, .94)
  light.addColorStop(0, '#ffe19b66')
  light.addColorStop(.48, '#ecc4772b')
  light.addColorStop(1, '#f0ba5800')
  context.fillStyle = light
  context.globalAlpha = glow / 13
  for (let edge = 0; edge < 10; edge += 1) {
    const top = .16 - edge * .006
    const bottom = .98 - edge * .028
    context.beginPath()
    context.moveTo(-top, 0)
    context.lineTo(top, 0)
    context.lineTo(bottom, 1)
    context.lineTo(-bottom, 1)
    context.closePath()
    context.fill()
  }
  context.restore()
}

function drawCurtain(context, screenWidth, width, height, direction, drop, fade, seconds, reducedMotion) {
  const size = Math.min(14, Math.max(8, screenWidth / 100))
  const stepX = size * .58
  const stepY = size * .82
  const inset = Math.min(screenWidth * .032, 65)
  const gather = height * .60
  const fall = reducedMotion ? 1 : drop
  const xAt = offset => direction === 1 ? offset : screenWidth - offset
  const edges = y => {
    if (y < gather) {
      const drape = clamp(y / gather)
      return [inset + width * .073 * drape ** 1.65, width * (1 - .81 * drape ** 1.62)]
    }
    const hang = clamp((y - gather) / (height - gather))
    const sway = reducedMotion ? 0 : Math.sin(seconds * 1.5 - hang * 3) * width * .023 * hang
    const outer = inset + width * (.073 - .055 * hang + .023 * Math.sin(hang * Math.PI)) + sway
    return [outer, width * (.19 + .085 * Math.sin(hang * Math.PI / 2))]
  }

  const rows = Math.max(1, Math.round(height / stepY))
  const pleats = screenWidth < 650 ? 7 : 11
  context.save()
  context.globalAlpha = drop * fade
  context.font = `bold ${size}px Consolas, monospace`
  for (let row = 0; row < rows; row += 1) {
    const y = (row + .5) / rows * height
    const [outer, span] = edges(y)
    const [nextOuter, nextSpan] = edges(y + stepY)
    const columns = Math.max(2, Math.round(span / stepX))
    const hang = clamp((y - gather) / (height - gather))
    for (let column = 0; column < columns; column += 1) {
      const across = (column + .5) / columns
      const fold = (across * pleats) % 1
      const slope = direction * (nextOuter - outer + across * (nextSpan - span))
      const line = Math.abs(slope) < stepX * .38 ? '|' : slope < 0 ? '/' : '\\'
      const border = column === 0 || column === columns - 1
      const hem = row === rows - 1
      const curve = (2 * across - 1) ** 2
      const drapeY = y - stepY * 1.2 * hang * curve
      const tone = Math.floor(fold * curtainFolds.length)
      context.fillStyle = hem ? '#aa6972' : border ? '#b66c77' : curtainFolds[tone]
      const glyph = hem ? (curve < .22 ? '_' : '.') : border || (tone > 0 && tone < 4) ? line : ':'
      context.fillText(glyph, xAt(outer + across * span), drapeY * fall)
    }
  }

  const [outer, span] = edges(gather)
  context.fillStyle = '#dea961'
  context.fillText('==o==', xAt(outer + span * .5), gather * fall)
  context.restore()
}

function drawGarland(context, width, seconds, fade, reducedMotion) {
  const unfold = ease((seconds - .45) / 1.4)
  const size = Math.min(17, Math.max(10, width / 63))
  const arcs = width >= 1000 ? 3 : 2
  const step = size * .64
  const span = width * .94
  context.save()
  context.font = `bold ${size}px Consolas, monospace`
  context.globalAlpha = fade * unfold
  for (let index = 0; (index + .5) * step < span; index += 1) {
    const along = (index + .5) * step
    const loop = (along / span * arcs) % 1
    const x = width * .03 + along
    const y = 7 + size * 1.35 * Math.sin(loop * Math.PI) * (reducedMotion ? 1 : unfold)
    const bulb = index % 9 === 4
    const berry = index % 13 === 6
    const glyph = bulb ? '*' : berry ? 'o' : loop < .5 ? '\\' : '/'
    context.fillStyle = bulb ? '#ffdb87' : berry ? '#ff6c82' : index % 2 ? '#397e58' : '#76bf82'
    context.shadowColor = context.fillStyle
    context.shadowBlur = bulb || berry ? 10 : 0
    context.fillText(glyph, x, y)
    if (!bulb && !berry && index % 2 === 0) context.fillText("'", x, y + size * .62)
  }
  context.restore()
}

function drawOrnaments(context, width, height, direction, seconds, fade, reducedMotion) {
  const size = Math.min(24, Math.max(13, width / 56))
  context.save()
  for (const [index, { x, length, art, color, stripe }] of ornaments.entries()) {
    const drop = ease((seconds - .63 - index * .12 - (direction === -1 ? .12 : 0)) / 1.25)
    if (drop <= 0) continue
    const anchor = width * (direction === 1 ? x : 1 - x)
    const y = height * length * (reducedMotion ? 1 : drop)
    const sway = reducedMotion ? 0 : Math.sin(seconds * 1.7 + index) * size * .45
    context.globalAlpha = fade * drop * .72
    context.fillStyle = '#f8c975'
    context.font = `bold ${size * .64}px Consolas, monospace`
    for (let link = size * .35; link <= y; link += size * .64) {
      context.fillText(':', anchor + sway * (link / y) ** 2, link)
    }
    context.globalAlpha = fade * drop
    context.fillStyle = context.shadowColor = color
    context.shadowBlur = 16
    context.font = `bold ${size}px Consolas, monospace`
    for (const [row, glyphs] of art.entries()) {
      const rowY = y + (row + 1) * size * .78
      if (!stripe) {
        context.fillText(glyphs, anchor + sway, rowY)
        continue
      }
      for (const [column, glyph] of Array.from(glyphs).entries()) {
        if (glyph === ' ') continue
        context.fillStyle = context.shadowColor = (row + column) % 3 ? color : stripe
        context.fillText(glyph, anchor + sway + (column - (glyphs.length - 1) / 2) * size * .6, rowY)
      }
    }
    context.shadowBlur = 0
  }
  context.restore()
}
