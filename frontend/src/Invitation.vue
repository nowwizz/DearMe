<script setup>
import { computed, ref } from 'vue'
import RouteMap from './RouteMap.vue'
import { formatClock, formatEndClock, formatWalk } from './api'

const props = defineProps({ plan: { type: Object, required: true }, saved: Boolean, overlaps: Array })
defineEmits(['edit', 'remove'])
const mapSearch = name => 'https://map.naver.com/p/search/' + encodeURIComponent(name)
const reasons = computed(() => Object.entries(props.plan.checks).filter(([key]) => !['비용', '예산'].includes(key)))
const photoSources = ref(new Map())
const photoSource = photo => photoSources.value.get(photo.url) ?? photo.thumbnail_url ?? photo.url

function recoverPhoto(photo) {
  photoSources.value.set(photo.url, photoSource(photo) === photo.url ? '' : photo.url)
}
</script>

<template>
  <article class="invitation">
    <div class="letter">
      <span class="letter-from">Dear. {{ plan.conditions.name || 'Me' }}</span>
      <h2>{{ plan.title }}</h2>
      <p>{{ plan.letter }}</p>
      <div class="letter-facts">
        <span>{{ plan.conditions.date }} · {{ formatClock(plan.conditions.start) }}~{{ formatEndClock(plan.conditions.end) }}</span>
        <span>{{ plan.conditions.region }}<template v-if="plan.conditions.companion"> · {{ plan.conditions.companion }}</template></span>
      </div>
      <small v-if="plan.mode === 'demo'" class="demo-note">시연용 초대장</small>
    </div>
    <div v-if="$slots.share" class="share-bar"><slot name="share" /></div>
    <div v-if="overlaps?.length" class="notice" role="status">
      <strong>시간이 겹치는 초대장</strong>
      <ul class="notes">
        <li v-for="row in overlaps" :key="row.id">{{ row.title }} · {{ formatClock(row.start) }}–{{ formatEndClock(row.end) }}</li>
      </ul>
    </div>
    <p v-if="plan.revalidation_required" class="notice" role="status">경로와 이용 조건을 다시 확인해야 하는 일정이에요.</p>
    <div class="invitation-body">
      <section>
        <h3>하루의 동선 · 방문지 {{ plan.stops.length }}곳</h3>
        <p v-if="plan.origin_label" class="muted">{{ plan.origin_label }}</p>
        <RouteMap :plan="plan" />
        <p v-if="plan.walking_seconds != null" class="map-stats">총 도보 {{ formatWalk(plan.walking_seconds) }} · 종료 예정 {{ plan.finishes }} · 여유 {{ plan.buffer_minutes }}분</p>
        <p v-else-if="plan.finishes" class="map-stats">예상 종료 {{ plan.finishes }} · 실제 도보 시간은 확인해 주세요.</p>
        <ul v-if="plan.legs.length" class="notes">
          <li v-for="(leg, index) in plan.legs" :key="index">{{ leg.origin }} → {{ leg.destination }} · {{ formatWalk(leg.seconds) }} · {{ leg.distance_m.toLocaleString('ko-KR') }}m</li>
        </ul>
        <ol class="timeline">
          <li v-for="(stop, index) in plan.stops" :key="stop.name + index">
            <b class="stop-index">{{ index + 1 }}</b>
            <div class="stop-copy"><small><span v-if="stop.meal" class="meal-label">{{ stop.meal }}</span><span v-else-if="stop.category === '카페' || stop.category === '행사'" class="visit-kind">{{ stop.category }}</span>{{ stop.arrives ? stop.arrives + '–' + stop.leaves + ' · ' : '' }}제안 체류 {{ stop.stay_minutes }}분</small>
              <h4>{{ stop.name }}</h4><p>{{ stop.reason }}</p>
              <p v-if="stop.address" class="muted">{{ stop.address }}</p>
              <small v-if="stop.hours">공개 이용 시간 {{ stop.hours }}</small>
              <small v-if="stop.closure">휴무 {{ stop.closure }}</small>
              <small v-if="stop.access === 'unknown'">방문 전 이용 가능 여부를 확인해 주세요.</small>
              <div v-if="plan.mode === 'live'" class="links">
                <a v-if="stop.source_url" :href="stop.source_url" target="_blank" rel="noreferrer">정보 출처 ↗</a>
                <a v-if="stop.provider === 'tmap' && !stop.point"
                  :href="mapSearch(plan.conditions.region + (stop.category === '카페' ? ' 카페' : ' 식당'))"
                  target="_blank" rel="noreferrer">근처 {{ stop.category === '카페' ? '카페' : '식당' }} 다시 찾기 ↗</a>
                <a v-else :href="mapSearch([stop.name, stop.address].filter(Boolean).join(' '))"
                  target="_blank" rel="noreferrer">지도에서 장소 찾기 ↗</a>
              </div>
            </div>
            <figure v-if="stop.photo && photoSource(stop.photo)" class="stop-photo">
              <a :href="stop.photo.url" target="_blank" rel="noreferrer">
                <img :src="photoSource(stop.photo)" :alt="stop.name + ' 대표 사진'" loading="lazy"
                  decoding="async" referrerpolicy="no-referrer" @error="recoverPhoto(stop.photo)" />
              </a>
              <figcaption>한국관광공사 · 공공누리 {{ stop.photo.license_type }}유형</figcaption>
            </figure>
          </li>
        </ol>
      </section>
      <section v-if="plan.weather">
        <h3>겨울 외출 준비</h3>
        <p>{{ plan.weather.guide }}</p>
        <p class="muted">기온 {{ plan.weather.temperature.join(' ~ ') }}°C · 체감 {{ plan.weather.apparent.join(' ~ ') }}°C</p>
        <p class="muted">{{ plan.weather.years.join(', ') }}년 · {{ plan.weather.period }}</p>
        <p class="muted">과거 자료를 참고했어요. 출발 전에 실제 예보를 확인해 주세요.</p>
        <p v-if="Object.values(plan.weather.missing).some(Boolean)" class="muted">일부 시각 또는 연도의 자료가 비어 있어요.</p>
        <a v-if="plan.weather.source_url" :href="plan.weather.source_url" target="_blank" rel="noreferrer">Open-Meteo ↗</a>
      </section>
      <section v-if="reasons.length || plan.exclusions.length">
        <h3>판단 근거</h3>
        <ul v-if="reasons.length" class="notes"><li v-for="[key, value] in reasons" :key="key"><strong>{{ key }}</strong> · {{ value }}</li></ul>
        <details v-if="plan.exclusions.length"><summary>제외한 후보와 이유</summary>
          <ul class="notes"><li v-for="item in plan.exclusions" :key="item">{{ item }}</li></ul>
        </details>
      </section>
      <section v-if="plan.songs.length">
        <h3>오늘의 음악</h3>
        <ul class="song-list"><li v-for="song in plan.songs" :key="song.title">
          <span aria-hidden="true">♫</span><div><a :href="song.url" target="_blank" rel="noreferrer">{{ song.title }} ↗</a><small>{{ song.artist }} · {{ song.reason }}</small></div>
        </li></ul>
      </section>
      <div v-if="saved" class="actions">
        <button class="button primary" @click="$emit('edit')">일정 수정</button>
        <button class="button outline" @click="$emit('remove')">삭제</button>
      </div>
    </div>
  </article>
</template>
