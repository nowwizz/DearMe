<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({ plan: { type: Object, required: true } })
const canvas = ref(null)
const mapElement = ref(null)
const tilesUnavailable = ref(false)
const stops = computed(() => props.plan.stops
  .map((stop, index) => ({ ...stop, number: index + 1 })).filter(stop => stop.point))
const latLng = ([lon, lat]) => [lat, lon]
let map
let layers
let observer

function drawMap() {
  if (!map) return
  layers.clearLayers()
  const lines = props.plan.legs.flatMap(leg => leg.lines).filter(line => line.length > 1)
  const positions = stops.value.map(stop => latLng(stop.point))
  for (const stop of stops.value) {
    const label = document.createElement('span')
    label.textContent = `${stop.number}. ${stop.name}`
    const icon = L.divIcon({ className: 'route-pin', html: String(stop.number), iconSize: [28, 28] })
    L.marker(latLng(stop.point), { icon, title: label.textContent }).bindTooltip(label).addTo(layers)
  }
  if (lines.length) {
    for (const line of lines) {
      const points = line.map(latLng)
      L.polyline(points, { color: '#164f43', weight: 5 }).addTo(layers)
      positions.push(...points)
    }
  } else if (positions.length > 1) {
    L.polyline(positions, { color: '#344d5e', weight: 3, dashArray: '5 7' }).addTo(layers)
  }
  if (positions.length) map.fitBounds(L.latLngBounds(positions), { padding: [28, 28], maxZoom: 16, animate: false })
}

function sizeMap() {
  if (!mapElement.value?.clientWidth || !mapElement.value?.clientHeight) return
  if (map) {
    map.invalidateSize({ pan: false, animate: false })
    return
  }
  map = L.map(mapElement.value, { scrollWheelZoom: false, maxZoom: 19 })
  layers = L.layerGroup().addTo(map)
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  }).addTo(map)
  let loaded = false
  tiles.on('tileload', () => { loaded = true; tilesUnavailable.value = false })
  tiles.on('load', () => { tilesUnavailable.value = !loaded })
  drawMap()
}

function removeMap() {
  observer?.disconnect()
  map?.remove()
  map = undefined
}

function draw() {
  if (!canvas.value) return
  const ctx = canvas.value.getContext('2d')
  const { width, height } = canvas.value
  const lines = props.plan.legs.flatMap(leg => leg.lines)
  const points = [...lines.flat(), ...stops.value.map(stop => stop.point)]
  ctx.fillStyle = '#0c121e'
  ctx.fillRect(0, 0, width, height)
  ctx.strokeStyle = '#202b3d'
  ctx.lineWidth = 1
  for (let x = 0; x < width; x += 32) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke()
  }
  for (let y = 0; y < height; y += 32) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
  }
  if (!points.length) return
  const xs = points.map(point => point[0])
  const ys = points.map(point => point[1])
  const midX = (Math.max(...xs) + Math.min(...xs)) / 2
  const midY = (Math.max(...ys) + Math.min(...ys)) / 2
  const lonScale = Math.cos(midY * Math.PI / 180)
  const scale = Math.min((width - 120) / (Math.max(.0005, Math.max(...xs) - Math.min(...xs)) * lonScale),
    (height - 110) / Math.max(.0005, Math.max(...ys) - Math.min(...ys)))
  const project = ([x, y]) => [width / 2 + (x - midX) * scale * lonScale, height / 2 - (y - midY) * scale]
  ctx.lineWidth = 5
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = '#8cdda7'
  for (const line of lines) {
    ctx.beginPath()
    line.forEach((point, index) => index ? ctx.lineTo(...project(point)) : ctx.moveTo(...project(point)))
    ctx.stroke()
  }
  for (const stop of stops.value) {
    const [x, y] = project(stop.point)
    ctx.fillStyle = '#c1b3fa'
    ctx.beginPath(); ctx.arc(x, y, 17, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = '#17142a'; ctx.font = 'bold 15px sans-serif'
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(stop.number, x, y + 1)
  }
  ctx.font = 'bold 16px sans-serif'; ctx.fillStyle = '#8cdda7'; ctx.fillText('↑ N', width - 36, 24)
}

onMounted(draw)
watch(mapElement, element => {
  removeMap()
  if (element) {
    tilesUnavailable.value = false
    observer = new ResizeObserver(sizeMap)
    observer.observe(element)
    sizeMap()
  }
}, { flush: 'post' })
watch(() => props.plan, () => {
  draw()
  if (mapElement.value?.clientWidth) drawMap()
}, { deep: true, flush: 'post' })
onUnmounted(removeMap)
</script>

<template>
  <figure v-if="stops.length" class="map">
    <canvas v-if="plan.mode === 'demo'" ref="canvas" width="720" height="290" role="img" aria-label="방문 순서와 경로를 좌표에 표시한 지도"></canvas>
    <div v-else ref="mapElement" class="route-map" role="region" aria-label="방문지와 경로 지도"></div>
    <figcaption>
      {{ plan.mode === 'demo' ? '시연용 좌표와 경로' : plan.legs.length ? 'TMAP 보행 경로' : stops.length > 1 ? '점선은 방문 순서만 표시해요. 실제 보행 경로는 확인해 주세요.' : '방문지 위치' }}
      <span v-if="tilesUnavailable"> · 배경 지도를 불러오지 못해 위치와 동선만 표시해요.</span>
    </figcaption>
  </figure>
  <p v-else class="muted">좌표가 등록된 방문지가 없어요. 아래 장소 링크에서 위치를 확인해 주세요.</p>
</template>
