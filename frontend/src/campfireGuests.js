const font = 'Consolas, monospace'

const fur = [null, null, '#e7cfae']
const boots = [null, null, '#51404a']
const scarf = [null, null, '#536e5d']

const santa = makeGuest([
  '           .--.',
  '         ./RRrr\\',
  '        /RRRRRrr\\',
  '       /wwwwwwrrrw',
  '       (hhEhhEh)',
  '       (WhcMhcW)',
  '        \\wwwww/',
  '        .\\"w"/.',
  '      ./RRRWRRR\\.',
  '     (rRjRRWjRRrrwH',
  '     (rrRRRWRRrrr)',
  '      \\rrbbgbbrr/',
  '       (rrr=rrr)',
  '       (kk) (kk)',
], {
  R: [null, null, '#b54450'],
  r: [null, null, '#913945'],
  j: ['.', '#ef9d8b', '#b54450'],
  w: fur,
  W: [null, null, '#f0ddbe'],
  h: [null, null, '#e4a884'],
  c: ['.', '#8a4c49', '#dda080'],
  E: ['.', '#46323b', '#e4a884'],
  M: ['v', '#825254', '#e4a884'],
  H: [')', '#ffd5ae', '#b87764'],
  b: boots,
  k: boots,
  g: ['+', '#ffe3a8', '#966441'],
}, { stepX: 7.9, stepY: 9, ink: '#e1a897' })

const rudolph = makeGuest([
  '      \\ /  \\ /',
  '       Y    Y',
  '       |    |',
  '     .dd\\__/dd.',
  '     /dfEdDDd/',
  '   @MffffdDD)',
  '    \\fffdDD/_.',
  '      \\ggggDDDdd.',
  '       (ssDDpDDDd)',
  '       (sdDDDDpdD)~',
  '       (dDDddDDDd)',
  '        (kk) (kk)',
], {
  d: [null, null, '#956044'],
  D: [null, null, '#b77e52'],
  f: [null, null, '#ddb185'],
  p: ['.', '#ffd1a0', '#b77e52'],
  E: ['.', '#443036', '#be8a64'],
  M: ['_', '#835150', '#ddb185'],
  '@': ['o', '#ff817d', '#bf4b54'],
  g: scarf,
  s: ['+', '#adc9a2', '#506759'],
  k: boots,
}, { stepX: 6.6, stepY: 8.6, ink: '#dfa570' })

const cat = makeGuest([
  '  /\\      /\\',
  ' /ac\\____/ca\\',
  '(aacEccccEcaa)',
  '=cWWWMWWWWWc=',
  ' \\ccccWcccc/    .',
  '  (gg+ggcc)    /t)',
  ' (acccWccaC)  /ta)',
  ' (acccWccaC)_/ta/',
  '  (pp) (pp)~--/',
], {
  a: [null, null, '#a77257'],
  c: [null, null, '#d1a279'],
  C: [null, null, '#ad7d60'],
  W: fur,
  p: fur,
  E: ['.', '#493138', '#d1a279'],
  M: ['w', '#855854', '#e7cfae'],
  g: scarf,
  t: [null, null, '#a26953'],
  '=': ['=', '#ffe2bf'],
}, { stepX: 5.7, stepY: 7.2, ink: '#e2ab88' })

function makeGuest(lines, palette, style) {
  const center = (Math.max(...lines.map(line => line.length)) - 1) / 2
  const cells = lines.flatMap((line, row) => [...line].flatMap((key, column) => {
    if (key === ' ') return []
    const [glyph, color, fill] = palette[key] ?? [key, style.ink]
    return [{ key, glyph, color, fill, x: column - center, y: row - lines.length + 1 }]
  }))
  const mouth = cells.find(cell => cell.key === 'M')
  return { ...style, cells, mouth, hand: cells.find(cell => cell.key === 'H') ?? mouth }
}

function guestPosition(cell, guest, x, floor, breath) {
  return [x + cell.x * guest.stepX, floor + cell.y * (guest.stepY + breath)]
}

function paintGuest(context, guest, x, floor, time, reduced) {
  const breath = reduced ? 0 : Math.sin(time * 1.5) * .13
  const blink = !reduced && time % 4.7 > 4.55
  const { stepX, stepY } = guest
  const opacity = context.globalAlpha
  const size = Math.ceil(stepX / .6)
  context.font = 'bold ' + size + 'px ' + font
  for (const cell of guest.cells) {
    if (!cell.fill) continue
    const [px, py] = guestPosition(cell, guest, x, floor, breath)
    context.fillStyle = cell.fill
    context.globalAlpha = opacity * .92
    context.fillRect(px - stepX / 2, py - stepY / 2, stepX + .25, stepY + .3)
  }
  context.globalAlpha = opacity
  for (const cell of guest.cells) {
    if (!cell.glyph) continue
    const [px, py] = guestPosition(cell, guest, x, floor, breath)
    context.fillStyle = cell.color
    if (cell.key === 'E' && !blink) {
      context.beginPath()
      context.ellipse(px, py, 1.15, 1.65, 0, 0, Math.PI * 2)
      context.fill()
      continue
    }
    if (cell.key === '@') {
      context.shadowColor = '#ff5a56'
      context.shadowBlur = 10
    }
    context.fillText(blink && cell.key === 'E' ? '-' : cell.glyph, px, py)
    context.shadowBlur = 0
  }
  return {
    mouth: guestPosition(guest.mouth, guest, x, floor, breath),
    hand: guestPosition(guest.hand, guest, x, floor, breath),
  }
}

function paintMarshmallow(context, { mouth, hand }, reach, time, reduced) {
  const phase = reduced ? .18 : (time % 5.5) / 5.5
  const motion = Math.max(0, Math.sin((phase - .50) * Math.PI * 2))
  const bite = motion * motion
  const tipX = hand[0] + reach * (1 - bite) + (mouth[0] - hand[0]) * bite
  const tipY = hand[1] - 23 * (1 - bite) + (mouth[1] - hand[1]) * bite - Math.sin(bite * Math.PI) * 10
  if (bite > .94) return

  context.save()
  context.strokeStyle = '#b78663'
  context.lineWidth = 1.8
  context.lineCap = 'round'
  context.beginPath()
  context.moveTo(...hand)
  context.lineTo(tipX, tipY)
  context.stroke()
  context.translate(tipX, tipY)
  context.rotate(reach > 0 ? -.21 : .21)

  const toasted = Math.min(1, phase * 2.4)
  const side = context.createLinearGradient(-7, 0, 7, 0)
  const warmEdge = reach > 0 ? 1 : 0
  side.addColorStop(1 - warmEdge, '#f6e6cf')
  side.addColorStop(.45, '#fff5df')
  side.addColorStop(warmEdge, 'hsl(34 62% ' + (80 - toasted * 21) + '%)')
  context.fillStyle = side
  context.beginPath()
  context.roundRect(-7, -10, 14, 14, 4)
  context.fill()

  context.fillStyle = '#fff8e9'
  context.beginPath()
  context.ellipse(0, -8, 6.7, 3.1, 0, 0, Math.PI * 2)
  context.fill()
  if (toasted > .4) {
    context.globalAlpha *= Math.min(1, (toasted - .4) / .38)
    context.fillStyle = '#d6955b'
    context.beginPath()
    context.ellipse(reach > 0 ? 2.4 : -2.4, -.5, 2.1, 1.35, -.4, 0, Math.PI * 2)
    context.fill()
  }
  context.restore()
}

export function paintCampfireGuests(context, x, y, time, opacity, reduced) {
  context.globalAlpha = opacity
  const arrive = reduced ? 0 : (1 - Math.min(1, time / .8)) ** 2 * 32
  const santaPose = paintGuest(context, santa, x - 176 - arrive, y + 25, time, reduced)
  const deerPose = paintGuest(context, rudolph, x + 180 + arrive, y + 6, time + 1.4, reduced)
  const catPose = paintGuest(context, cat, x + 150 + arrive * .45, y + 43, time + 2.7, reduced)
  paintMarshmallow(context, santaPose, 67, time, reduced)
  paintMarshmallow(context, deerPose, -62, time + 1.4, reduced)
  paintMarshmallow(context, catPose, -44, time + 2.7, reduced)
}
