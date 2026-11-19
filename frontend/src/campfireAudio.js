function crackle(samples, offset, length, volume, rate) {
  let low = 0
  for (let i = 0; i < length; i += 1) {
    const noise = Math.random() * 2 - 1
    low += (noise - low) * .28
    const age = i / length
    const pop = Math.sin(i / rate * 350 * Math.PI * 2) * Math.exp(-age * 23)
    const envelope = Math.min(1, i / 12) * (1 - age) ** 3
    samples[(offset + i) % samples.length] += ((noise - low * .65) * .7 + pop * .3) * envelope * volume
  }
}

export function startCampfireAudio(context, at) {
  const rate = 24000
  const buffer = context.createBuffer(1, rate * 11, rate)
  const samples = buffer.getChannelData(0)
  let low = 0
  for (let i = 0; i < samples.length; i += 1) {
    low += (Math.random() * 2 - 1 - low) * .035
    const seam = Math.min(1, i / 300, (samples.length - 1 - i) / 300)
    samples[i] = low * .18 * seam
  }
  for (let time = .07; time < 11; time += .09 + Math.random() * .32) {
    crackle(samples, Math.floor(time * rate), Math.floor((.026 + Math.random() * .065) * rate),
      .065 + Math.random() ** 2 * .24, rate)
  }

  const bed = context.createBufferSource()
  const gain = context.createGain()
  bed.buffer = buffer
  bed.loop = true
  bed.connect(gain).connect(context.destination)
  gain.gain.value = 0
  gain.gain.setValueAtTime(0, at)
  gain.gain.linearRampToValueAtTime(.63, at + .55)
  bed.start(at)

  function pop() {
    const burst = context.createBuffer(1, rate * .4, rate)
    const sparks = burst.getChannelData(0)
    crackle(sparks, 0, Math.floor(rate * .17), .44, rate)
    crackle(sparks, Math.floor(rate * .094), Math.floor(rate * .16), .25, rate)
    crackle(sparks, Math.floor(rate * .21), Math.floor(rate * .12), .16, rate)
    const source = context.createBufferSource()
    source.buffer = burst
    source.connect(gain)
    source.start()
  }

  function stop() {
    if (context.state !== 'running') {
      gain.disconnect()
      bed.stop()
      return
    }
    const now = context.currentTime
    gain.gain.cancelScheduledValues(now)
    gain.gain.setTargetAtTime(0, now, .025)
    bed.addEventListener('ended', () => gain.disconnect(), { once: true })
    bed.stop(now + .14)
  }

  return { pop, stop }
}
