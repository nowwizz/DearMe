<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { renderSilentNight } from './holidayMusic'

const enabled = ref(true)
const unavailable = ref(false)
const button = ref(null)
const label = computed(() => unavailable.value ? '음악 재생 다시 시도' :
  enabled.value ? '고요한 밤 거룩한 밤 일시정지' : '고요한 밤 거룩한 밤 재생')
let context
let source
let rendering
let disposed = false

async function startMusic() {
  try {
    context ??= new AudioContext()
    // A blocked resume can stay pending until the browser sees a user gesture.
    await context.resume()
    if (disposed || !enabled.value) return
    removeGestureListeners()
    if (source) return

    rendering ??= renderSilentNight()
    const buffer = await rendering
    if (disposed || !enabled.value || source) return
    source = context.createBufferSource()
    source.buffer = buffer
    source.loop = true
    source.connect(context.destination)
    source.start()
  } catch {
    rendering = undefined
    if (!disposed && enabled.value) unavailable.value = true
  }
}

function startOnGesture(event) {
  if (enabled.value && !event.composedPath().includes(button.value)) {
    unavailable.value = false
    startMusic()
  }
}

function removeGestureListeners() {
  window.removeEventListener('click', startOnGesture, true)
  window.removeEventListener('keydown', startOnGesture, true)
}

function toggle() {
  enabled.value = unavailable.value || !enabled.value
  unavailable.value = false
  if (enabled.value) startMusic()
  else context?.suspend().catch(() => {})
}

onMounted(() => {
  window.addEventListener('click', startOnGesture, true)
  window.addEventListener('keydown', startOnGesture, true)
  startMusic()
})

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
