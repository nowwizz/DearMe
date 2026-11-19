<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { renderSilentNight } from './holidayMusic'
import { startCampfireAudio } from './campfireAudio'

const enabled = ref(true)
const unavailable = ref(false)
const button = ref(null)
const campfire = ref(false)
const label = computed(() => unavailable.value ? '음악 재생 다시 시도' :
  campfire.value ? (enabled.value ? '모닥불 소리 끄기' : '모닥불 소리 켜기') :
  enabled.value ? '고요한 밤 거룩한 밤 일시정지' : '고요한 밤 거룩한 밤 재생')
let context
let source
let musicGain
let rendering
let fireAt
let campfireAudio
let disposed = false

async function startAudio() {
  try {
    context ??= new AudioContext()
    // A blocked resume can stay pending until the browser sees a user gesture.
    await context.resume()
    if (disposed || !enabled.value) return
    removeGestureListeners()
    if (campfire.value) {
      if (!campfireAudio) {
        const delay = Math.max(0, (fireAt - performance.now()) / 1000)
        const now = context.currentTime
        if (musicGain) {
          musicGain.gain.cancelScheduledValues(now)
          musicGain.gain.setValueAtTime(1, now)
          musicGain.gain.linearRampToValueAtTime(0, now + Math.min(delay, .55))
        }
        campfireAudio = startCampfireAudio(context, now + delay)
      }
      return
    }
    if (source) return

    rendering ??= renderSilentNight()
    const buffer = await rendering
    if (disposed || !enabled.value || source || campfire.value) return
    musicGain = context.createGain()
    source = context.createBufferSource()
    source.buffer = buffer
    source.loop = true
    source.connect(musicGain).connect(context.destination)
    source.start()
  } catch {
    rendering = undefined
    if (!disposed && enabled.value) unavailable.value = true
  }
}

function startOnGesture(event) {
  if (enabled.value && !event.composedPath().includes(button.value)) {
    unavailable.value = false
    startAudio()
  }
}

function removeGestureListeners() {
  window.removeEventListener('click', startOnGesture, true)
  window.removeEventListener('keydown', startOnGesture, true)
}

function toggle() {
  enabled.value = unavailable.value || !enabled.value
  unavailable.value = false
  if (enabled.value) startAudio()
  else context?.suspend().catch(() => {})
}

onMounted(() => {
  window.addEventListener('click', startOnGesture, true)
  window.addEventListener('keydown', startOnGesture, true)
  startAudio()
})

function lightCampfire(delay) {
  campfire.value = true
  fireAt = performance.now() + delay * 1000
  if (enabled.value) startAudio()
}

async function stokeCampfire() {
  if (!enabled.value) return
  await startAudio()
  if (!disposed && enabled.value && campfire.value) campfireAudio?.pop()
}

function returnToTree() {
  campfire.value = false
  unavailable.value = false
  campfireAudio?.stop()
  campfireAudio = undefined
  if (musicGain) {
    const now = context.currentTime
    musicGain.gain.cancelScheduledValues(now)
    musicGain.gain.setTargetAtTime(1, now, .055)
  }
  if (enabled.value) startAudio()
}

defineExpose({ lightCampfire, stokeCampfire, returnToTree })

onUnmounted(() => {
  disposed = true
  removeGestureListeners()
  if (context && context.state !== 'closed') context.close().catch(() => {})
})
</script>

<template>
  <button ref="button" class="music-toggle" type="button" :aria-label="label" :title="label"
    :aria-pressed="enabled && !unavailable" @click="toggle">
    <span aria-hidden="true">♫</span>
  </button>
</template>
