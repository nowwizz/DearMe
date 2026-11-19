export const giftEffectSeconds = 1.25
const still = { shake: 0, lift: 0, glow: 0 }

export function giftEffect(effect, seconds, reducedMotion) {
  if (!effect) return still
  const age = seconds - effect.start
  const progress = Math.min(1, age / (effect.open ? giftEffectSeconds : .55))
  if (progress >= 1) return still
  if (!effect.open) {
    return {
      shake: reducedMotion ? 0 : Math.sin(age * 55) * (1 - progress),
      lift: 0, glow: 0,
    }
  }
  const lift = Math.sin(Math.PI * Math.min(1, progress * 1.1)) ** .7
  const flash = Math.max(0, 1 - Math.abs(progress - .24) / .24)
  return { shake: 0, lift: reducedMotion ? .65 : lift, glow: Math.max(lift * .52, flash) }
}

export function paintBurst(context, x, y, radius, strength, color) {
  if (strength <= 0) return
  context.save()
  context.fillStyle = context.shadowColor = color
  context.shadowBlur = 16
  context.font = 'bold 13px Consolas, monospace'
  context.globalAlpha = strength
  for (let index = 0; index < 9; index += 1) {
    const angle = index * Math.PI * 2 / 9
    const length = radius * (.7 + (index % 3) * .15)
    context.fillText('*+.'[index % 3], x + Math.cos(angle) * length, y + Math.sin(angle) * length)
  }
  context.restore()
}

export function paintGiftFlash(context, x, y, radius, { lift, glow }, reducedMotion) {
  if (glow <= 0) return
  context.save()
  const halo = context.createRadialGradient(x, y, 0, x, y, radius)
  halo.addColorStop(0, '#ffffe8eb')
  halo.addColorStop(.22, '#ffe8a8b0')
  halo.addColorStop(.58, '#ffc66243')
  halo.addColorStop(1, '#ffc66200')
  context.globalAlpha = glow
  context.fillStyle = halo
  context.fillRect(x - radius, y - radius, radius * 2, radius * 2)
  context.fillStyle = context.shadowColor = '#fff9d9'
  context.shadowBlur = 18
  context.font = `bold ${Math.max(16, radius * .62)}px Consolas, monospace`
  context.fillText('*', x, y)
  context.restore()
  const spread = reducedMotion ? .8 : .62 + lift * .44
  paintBurst(context, x, y - radius * .25, radius * spread, Math.min(1, glow * 1.3), '#fff0b2')
}
