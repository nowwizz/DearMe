// Franz Gruber's 1818 melody, with an original soft keyboard accompaniment.
const opening = [[67, 1.5], [69, .5], [67, 1], [64, 3]]
const middle = [
  [[69, 3], [69, 3]], [[72, 1.5], [71, .5], [69, 1], [67, 3]],
  [[69, 1.5], [67, .5], [64, 4]],
]
const melody = [
  opening, opening,
  [[74, 3], [74, 3]], [[71, 6]],
  [[72, 3], [72, 3]], [[67, 6]],
  ...middle, ...middle,
  [[74, 3], [74, 1], [77, 1], [74, 1]],
  [[71, 3], [72, 6]], [[76, 6]],
  [[72, 1.5], [67, .5], [64, 1], [67, 1.5], [65, .5], [62, 1]], [[60, 6]],
]
const harmony = [
  'C', 'C', 'G', 'G', 'C', 'C', 'F', 'F', 'C', 'F', 'F', 'C',
  'G', 'G', 'C', 'C', 'C', 'G', 'C',
]
const chords = { C: [48, 55, 64], F: [41, 53, 60], G: [43, 55, 62] }
const beat = .36

function playNote(context, channel, pitch, time, length, loudness, type) {
  const oscillator = context.createOscillator()
  const envelope = context.createGain()
  oscillator.type = type
  oscillator.frequency.value = 440 * 2 ** ((pitch - 69) / 12)
  envelope.gain.setValueAtTime(0, time)
  envelope.gain.linearRampToValueAtTime(loudness, time + .018)
  envelope.gain.exponentialRampToValueAtTime(loudness * .32, time + Math.max(.09, length * .75))
  envelope.gain.exponentialRampToValueAtTime(.0001, time + length + .45)
  oscillator.connect(envelope).connect(channel)
  oscillator.start(time)
  oscillator.stop(time + length + .46)
}

export function renderSilentNight() {
  const sampleRate = 22050
  const notes = melody.flat()
  const duration = notes.reduce((total, [, beats]) => total + beats, 0) * beat
  const context = new OfflineAudioContext(1, Math.ceil((duration + 1.65) * sampleRate), sampleRate)
  const channel = context.createGain()
  channel.gain.value = .54
  channel.connect(context.destination)

  let time = .22
  for (const [pitch, beats] of notes) {
    playNote(context, channel, pitch - 2, time, beats * beat * .93, .24, 'triangle')
    playNote(context, channel, pitch + 10, time, Math.min(beats * beat, .45), .023, 'sine')
    time += beats * beat
  }
  for (const [bar, chord] of harmony.entries()) {
    for (const [index, pitch] of chords[chord].entries()) {
      const time = .22 + (bar * 6 + index * 2) * beat
      if (time >= duration) break
      playNote(context, channel, pitch - 2, time, .63, index ? .053 : .085, 'sine')
    }
  }
  return context.startRendering()
}
