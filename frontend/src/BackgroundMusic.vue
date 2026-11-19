<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { renderSilentNight } from './holidayMusic'

const playing = ref(false)
const loading = ref(false)
const unavailable = ref(false)
const label = computed(() => unavailable.value ? '음악 재생 다시 시도' :
  playing.value ? '고요한 밤 거룩한 밤 일시정지' : '고요한 밤 거룩한 밤 재생')
let context
let source
let disposed = false

async function toggle() {
  if (loading.value) return
  loading.value = true
  unavailable.value = false
  try {
    if (playing.value) {
      await context.suspend()
      playing.value = false
      return
    }
    context ??= new AudioContext()
    await context.resume()
    if (!source) {
      const buffer = await renderSilentNight()
      if (disposed) return
      source = context.createBufferSource()
      source.buffer = buffer
      source.loop = true
      source.connect(context.destination)
      source.start()
    }
    playing.value = true
  } catch {
    if (!disposed) unavailable.value = true
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
  disposed = true
  if (context && context.state !== 'closed') context.close().catch(() => {})
})
</script>

<template>
  <button class="music-toggle" type="button" :aria-label="label" :title="label"
    :aria-pressed="playing" :disabled="loading" @click="toggle">
    <span aria-hidden="true">♫</span>
  </button>
</template>
