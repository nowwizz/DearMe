<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { api, formatClock, formatEndClock, formatStamp } from './api'
import EventList from './EventList.vue'
import Invitation from './Invitation.vue'
import InvitationShare from './InvitationShare.vue'
import AsciiTree from './AsciiTree.vue'
import BackgroundMusic from './BackgroundMusic.vue'
import TerminalBar from './TerminalBar.vue'

const assistantName = '메리'
const opening = { role: 'assistant', text: '안녕! 나는 크리스마스 코스를 추천해주는 메리야. 크리스마스에 어느 역 근처에서 뭘 하고 싶어?' }
const tabs = [{ id: 'chat', title: '대화하기' }, { id: 'archive', title: '초대장 보관함' }, { id: 'logs', title: '실행 기록' }]
const sharedId = new URLSearchParams(window.location.search).get('invite')
const current = ref('chat')
const sharedPlan = ref(null)
const sharedError = ref('')
const sharedDialog = ref(null)
const mainPage = ref(null)
const mode = ref('live')
const messages = ref([opening])
const conditions = ref({})
const eventRows = ref([])
const session = ref(null)
const runId = ref(null)
const text = ref('')
const generating = ref(false)
const archive = ref([])
const logSessions = ref([])
const activeLog = ref(null)
const logEvents = ref([])
const invitation = ref(null)
const invitationDialog = ref(null)
const savedDraft = ref(null)
const savingRun = ref(null)
const saveError = ref('')
const saved = ref(null)
const editing = ref(null)
const confirmation = ref(null)
const overlap = ref([])
const feedback = ref('')
const error = ref('')
const scrollLog = ref(null)
const terminal = ref(null)
const input = ref(null)
const scene = ref(null)
const sceneAudio = ref(null)
const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
const motionReduced = ref(motionPreference.matches)
const scenePaused = ref(motionReduced.value)
const skipTreeIntro = ref(Boolean(sharedId))
const snowTree = Math.random() < .05
const syncMotionPreference = event => {
  motionReduced.value = event.matches
  scenePaused.value = event.matches
}

const labels = { name: '받는 사람', date: '날짜', start: '시작', end: '종료', region: '활동 기준', origin: '출발 장소', companion: '동행', mood: '분위기', activities: '활동', food: '음식', music: '음악', budget: '예산', party_size: '인원', walking_limit: '걷기 제한', avoids: '피하고 싶어요', cold_sensitive: '추위', indoor: '실내외' }
const tags = computed(() => Object.entries(labels).flatMap(([key, label]) => {
  const value = conditions.value[key]
  if (value == null || Array.isArray(value) && !value.length) return []
  const display = key === 'budget' ? value.toLocaleString('ko-KR') + '원 ' + ({ total: '전체', person: '1인' }[conditions.value.budget_basis] || '')
    : key === 'walking_limit' ? value + '분' : key === 'party_size' ? value + '명'
    : key === 'start' ? formatClock(value) : key === 'end' ? formatEndClock(value) : key === 'cold_sensitive' ? value ? '민감함' : '괜찮음'
    : key === 'indoor' ? { mostly_indoor: '실내 위주', balanced: '실내외 반반', mostly_outdoor: '야외 위주' }[value]
    : Array.isArray(value) ? value.join(', ') : value
  return [{ key, label, value: display }]
}))
const samplePrompts = [
  { label: '혼자 보내기', request: '크리스마스에 종로3가역 근처에서 오후 2시부터 6시까지 혼자 조용한 전시와 카페에 가고 싶어. 도보는 30분 이내, 재즈가 좋아.' },
  { label: '친구와 함께', request: '크리스마스에 종로3가역 근처에서 오후 2시부터 6시까지 친구랑 2명이서 전시랑 카페에 갈래. 도보는 10분 이내야.' },
  { label: '실내 위주', request: '크리스마스에 종로3가역 근처에서 오후 1시부터 5시까지 혼자 보낼래. 추위를 많이 타서 실내 위주로, 문화시설 한 곳을 넣어 줘.' },
]
const lastEvent = computed(() => eventRows.value.at(-1))
const stageName = { analysis: '조건을 살피는 중', plan: '작업 순서를 정하는 중', execute: '장소와 경로를 조회하는 중', judge: '조건을 비교하는 중', replan: '다른 후보를 찾는 중', respond: '편지를 쓰는 중' }

function resetChat(nextMode = mode.value) {
  if (generating.value) return
  mode.value = nextMode
  session.value = null
  conditions.value = {}
  eventRows.value = []
  messages.value = [opening]
  runId.value = null
  invitation.value = null
  savedDraft.value = null
  saveError.value = ''
  saved.value = null
  overlap.value = []
  feedback.value = ''
  error.value = ''
  text.value = ''
  current.value = 'chat'
}

async function submit(value = text.value) {
  const message = value.trim()
  if (!message || generating.value) return
  messages.value.push({ role: 'user', text: message })
  text.value = ''
  eventRows.value = []
  generating.value = true
  feedback.value = ''
  overlap.value = []
  error.value = ''
  runId.value = null
  invitation.value = null
  savedDraft.value = null
  saveError.value = ''
  saved.value = null
  await scrollToLatest()
  let followReply = false
  try {
    const accepted = await api('/chat', { method: 'POST', body: JSON.stringify({ message, session_id: session.value, mode: mode.value }) })
    session.value = accepted.session_id
    runId.value = accepted.run_id
    const deadline = Date.now() + 240000
    while (Date.now() < deadline) {
      const run = await api('/chat/' + runId.value + '?after=' + (lastEvent.value?.sequence || 0))
      eventRows.value.push(...run.events)
      if (run.result) {
        const log = scrollLog.value
        followReply = !log || log.scrollHeight - log.clientHeight - log.scrollTop <= 32
        conditions.value = run.result.conditions
        invitation.value = run.result.plan
        messages.value.push({ role: 'assistant', text: run.result.message, warnings: run.result.warnings })
        break
      }
      await new Promise(resolve => setTimeout(resolve, 450))
    }
    if (messages.value.at(-1).role === 'user') throw new Error('처리가 늦어지고 있어요. 실행 기록에서 진행 상태를 확인해 주세요.')
  } catch (ex) {
    error.value = ex.message
  } finally {
    generating.value = false
    if (followReply) await scrollToLatest()
  }
}

async function scrollToLatest() {
  await nextTick()
  if (scrollLog.value) scrollLog.value.scrollTop = scrollLog.value.scrollHeight
}

function submitFromKeyboard(event) {
  if (event.isComposing) return
  event.preventDefault()
  submit()
}

function useExample() {
  resetChat('demo')
  submit(samplePrompts[0].request)
}

function usePrompt(request) {
  text.value = request
  input.value?.focus()
}

function returnToTree() {
  scene.value?.returnToTree()
  sceneAudio.value?.returnToTree()
}

async function go(tab, planId) {
  if (current.value === 'chat' && tab !== 'chat') skipTreeIntro.value = true
  current.value = tab
  feedback.value = ''
  error.value = ''
  editing.value = null
  confirmation.value = null
  if (tab === 'chat') return
  try {
    if (tab === 'archive') {
      saved.value = null
      overlap.value = []
      archive.value = await api('/plans')
      if (planId && current.value === 'archive') await openSaved(planId)
    } else {
      logSessions.value = await api('/logs')
      activeLog.value = null
      logEvents.value = []
    }
  } catch (ex) { error.value = ex.message }
}

async function savePlan() {
  const id = runId.value
  if (savedDraft.value || !id || savingRun.value === id) return
  savingRun.value = id
  saveError.value = ''
  try {
    const row = await api('/plans', { method: 'POST', body: JSON.stringify({ run_id: id }) })
    if (runId.value === id) savedDraft.value = row
  } catch (ex) {
    if (runId.value === id) saveError.value = ex.message
  } finally {
    if (savingRun.value === id) savingRun.value = null
  }
}

function viewSavedDraft() {
  if (!savedDraft.value) return
  invitationDialog.value?.close()
  return go('archive', savedDraft.value.id)
}

async function openSaved(id) {
  try {
    saved.value = await api('/plans/' + id)
    overlap.value = saved.value.overlaps
    editing.value = null
    error.value = ''
  } catch (ex) { error.value = ex.message }
}

async function openSharedInvitation() {
  try {
    const row = await api('/plans/' + encodeURIComponent(sharedId))
    sharedPlan.value = row.plan
  } catch {
    sharedError.value = '이 초대장을 열 수 없어요. 보낸 사람에게 링크를 다시 받아 주세요.'
  }
}

function editPlan() {
  const row = saved.value
  editing.value = { title: row.title, date: row.date, start: formatClock(row.start), end: formatClock(row.end),
    stops: row.plan.stops.map(stop => ({ name: stop.name, stay_minutes: stop.stay_minutes })) }
}

async function updatePlan() {
  try {
    saved.value = await api('/plans/' + saved.value.id, { method: 'PATCH', body: JSON.stringify(editing.value) })
    archive.value = await api('/plans')
    overlap.value = saved.value.overlaps
    editing.value = null
    feedback.value = '일정을 수정했어요.'
    error.value = ''
  } catch (ex) { error.value = ex.message }
}

async function openLog(id) {
  try {
    logEvents.value = (await api('/logs/' + id)).events
    activeLog.value = id
    error.value = ''
  } catch (ex) { error.value = ex.message }
}

async function confirmDelete() {
  const deleting = confirmation.value
  confirmation.value = null
  try {
    if (deleting === 'plan') {
      await api('/plans/' + saved.value.id, { method: 'DELETE' })
      saved.value = null
      overlap.value = []
      archive.value = await api('/plans')
      feedback.value = '초대장을 삭제했어요.'
    } else {
      await api('/logs/' + activeLog.value, { method: 'DELETE' })
      activeLog.value = null
      logEvents.value = []
      logSessions.value = await api('/logs')
      feedback.value = '선택한 대화의 실행 기록을 삭제했어요.'
    }
  } catch (ex) { error.value = ex.message }
}

onMounted(() => {
  mainPage.value?.focus({ preventScroll: true })
  motionPreference.addEventListener('change', syncMotionPreference)
  if (sharedId) {
    sharedDialog.value?.showModal()
    openSharedInvitation()
  }
})
onUnmounted(() => motionPreference.removeEventListener('change', syncMotionPreference))
</script>

<template>
  <header class="topbar">
    <a class="brand" href="#" @click.prevent="go('chat')">Dear. Me</a>
    <nav aria-label="주 메뉴">
      <button v-for="tab in tabs" :key="tab.id" :class="{ active: current === tab.id }"
        :aria-current="current === tab.id ? 'page' : undefined" :disabled="generating && current !== tab.id" @click="go(tab.id)">
        {{ tab.title }}
      </button>
    </nav>
  </header>

  <main ref="mainPage" :class="current === 'chat' ? 'chat-page' : 'library-page'" tabindex="-1">
    <template v-if="current === 'chat'">
      <div class="chat-stage">
        <AsciiTree ref="scene" :paused="scenePaused" :reduced-motion="motionReduced" :skip-intro="skipTreeIntro"
          :snow-tree="snowTree" :terminal="terminal" @light-campfire="sceneAudio?.lightCampfire($event)"
          @stoke-campfire="sceneAudio?.stokeCampfire()" />
        <BackgroundMusic ref="sceneAudio" />
        <button v-if="scene?.campfireReady" class="tree-return" type="button" aria-label="트리로 돌아가기"
          title="트리로 돌아가기" @click="returnToTree">
          <span class="tree-return-icon" aria-hidden="true"></span>
        </button>
        <button class="scene-toggle" type="button" :aria-label="scenePaused ? '애니메이션 재생' : '애니메이션 일시정지'"
          :title="scenePaused ? '애니메이션 재생' : '애니메이션 일시정지'" @click="scenePaused = !scenePaused">
          <span class="scene-icon" :class="{ play: scenePaused }" aria-hidden="true"></span>
        </button>
        <button v-if="invitation" class="arrival-envelope" type="button" aria-haspopup="dialog"
          aria-controls="invitation-dialog" @click="invitationDialog?.showModal()">
          <span class="envelope-art" aria-hidden="true">
            <span class="envelope-paper"></span>
            <span class="envelope-pocket"></span>
            <span class="envelope-seal">✦</span>
          </span>
          <span class="envelope-caption">
            <strong>초대장이 도착했어요</strong>
            <small>봉투 열기</small>
          </span>
        </button>
        <section ref="terminal" class="terminal-window chat-panel" aria-labelledby="chat-title">
          <TerminalBar>
            <h2 id="chat-title" aria-label="메리와 대화">merry <span>—</span> zsh</h2>
            <template #actions>
              <div class="chat-actions">
                <span v-if="mode === 'demo'" class="demo-label">시연 모드</span>
                <button v-else class="quiet" :disabled="generating" @click="useExample" aria-label="예시 초대장 받아보기">예시 초대장</button>
                <button class="quiet" :disabled="generating" @click="resetChat('live')">새 대화</button>
              </div>
            </template>
          </TerminalBar>
          <div ref="scrollLog" class="messages" role="log" aria-label="대화 내용" aria-live="polite" tabindex="0">
            <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
              <span class="speaker">{{ message.role === 'assistant' ? assistantName : '나' }}</span>
              <div><p>{{ message.text }}</p>
                <details v-if="message.warnings?.length"><summary>확인할 내용 {{ message.warnings.length }}건</summary>
                  <ul class="notes"><li v-for="line in message.warnings" :key="line">{{ line }}</li></ul>
                </details>
              </div>
            </div>
            <div v-if="generating" class="message assistant">
              <span class="speaker">{{ assistantName }}</span>
              <div><p role="status"><span class="pulse"></span>{{ stageName[lastEvent?.stage] || '편지를 준비하는 중' }}…</p></div>
            </div>
          </div>
          <div v-if="messages.length === 1" class="chips" aria-label="대화 예시">
            <button v-for="item in samplePrompts" :key="item.label" :disabled="generating" type="button" @click="usePrompt(item.request)">
              <span aria-hidden="true">[</span>{{ item.label }}<span aria-hidden="true">]</span>
            </button>
          </div>
          <form class="composer" @submit.prevent="submit()">
            <span class="prompt-mark" aria-hidden="true">~ <b>%</b></span>
            <textarea ref="input" v-model="text" aria-label="크리스마스 계획 메시지"
              placeholder="크리스마스 계획을 말해 주세요" enterkeyhint="send" rows="1" maxlength="2000" @keydown.enter.exact="submitFromKeyboard"></textarea>
          </form>
          <details v-if="tags.length || eventRows.length" class="chat-details">
            <summary>조건과 진행 기록</summary>
            <dl v-if="tags.length" class="tags"><div v-for="tag in tags" :key="tag.key"><dt>{{ tag.label }}</dt><dd>{{ tag.value }}</dd></div></dl>
            <EventList v-if="eventRows.length" :events="eventRows" />
          </details>
        </section>
      </div>
      <dialog v-if="invitation" ref="invitationDialog" id="invitation-dialog" class="terminal-window terminal-library invitation-dialog"
        aria-labelledby="invitation-dialog-title">
        <div class="invitation-toolbar">
          <TerminalBar>
            <h2 id="invitation-dialog-title" tabindex="-1" autofocus>크리스마스 초대장</h2>
            <template #actions>
              <button class="quiet dialog-close" type="button" @click="invitationDialog?.close()">닫기</button>
            </template>
          </TerminalBar>
          <div class="dialog-save-bar">
            <p v-if="savedDraft" class="save-confirmation" role="status">초대장 보관함에 넣었어요.</p>
            <p v-else-if="saveError" class="save-error" role="alert">{{ saveError }}</p>
            <button v-if="savedDraft" class="button outline" type="button" @click="viewSavedDraft">보관함에서 보기</button>
            <button v-else class="button primary" type="button"
              :disabled="savingRun !== null && savingRun === runId" @click="savePlan">
              {{ savingRun !== null && savingRun === runId ? '저장 중…' : '초대장 저장' }}
            </button>
          </div>
          <div v-if="savedDraft" class="share-bar"><InvitationShare :entry="savedDraft" /></div>
        </div>
        <Invitation :plan="invitation" :overlaps="savedDraft?.overlaps" />
      </dialog>
    </template>

    <section v-else class="terminal-window terminal-library" aria-labelledby="library-title">
      <TerminalBar>
        <h1 id="library-title">{{ current === 'archive' ? '초대장 보관함' : '실행 기록' }}</h1>
      </TerminalBar>
      <div v-if="current === 'archive'" class="subgrid" :class="{ 'has-records': archive.length }">
        <section class="list-panel">
          <h2><span aria-hidden="true">~ %</span> 저장된 초대장</h2>
          <p v-if="!archive.length" class="muted">보관함이 비어 있어요.</p>
          <button v-for="item in archive" :key="item.id" class="list-item" :class="{ selected: saved?.id === item.id }"
            :aria-current="saved?.id === item.id || undefined" @click="openSaved(item.id)">
            <strong>{{ item.title }}</strong><small>{{ item.date }} · {{ formatClock(item.start) }}–{{ formatEndClock(item.end) }}</small>
            <small>{{ item.stops.join(' → ') }}</small><small>보관 {{ formatStamp(item.created_at) }}</small>
            <small v-if="item.mode === 'demo'">시연용</small><small v-if="item.revalidation_required">재확인 필요</small>
          </button>
        </section>
        <form v-if="editing" class="edit-form" @submit.prevent="updatePlan">
          <h2>일정 수정</h2>
          <label>제목<input v-model="editing.title" required maxlength="160"></label>
          <div class="form-row"><label>날짜<input v-model="editing.date" type="date" required></label>
            <label>시작<input v-model="editing.start" type="time" required></label><label>종료<input v-model="editing.end" type="time" required></label></div>
          <fieldset><legend>방문 순서</legend>
            <div v-for="(stop, index) in editing.stops" :key="index" class="form-row">
              <label>장소 {{ index + 1 }}<input v-model="stop.name" required maxlength="160"></label>
              <label>체류 시간 <input v-model.number="stop.stay_minutes" type="number" min="1" max="1440" required></label>
              <button type="button" class="quiet" :disabled="editing.stops.length === 1" @click="editing.stops.splice(index, 1)">빼기</button>
            </div>
            <button type="button" class="button outline" :disabled="editing.stops.length >= 5" @click="editing.stops.push({ name: '', stay_minutes: 30 })">장소 추가</button>
          </fieldset>
          <div class="actions"><button class="button primary">변경 저장</button><button type="button" class="button outline" @click="editing = null">취소</button></div>
        </form>
        <Invitation v-else-if="saved" :key="saved.id" :plan="saved.plan" :overlaps="overlap" saved @edit="editPlan" @remove="confirmation = 'plan'">
          <template #share><InvitationShare :entry="saved" /></template>
        </Invitation>
        <p v-else-if="archive.length" class="library-instruction">열어 볼 초대장을 선택해 주세요.</p>
      </div>
      <div v-else class="subgrid" :class="{ 'has-records': logSessions.length }">
        <section class="list-panel">
          <h2><span aria-hidden="true">~ %</span> 대화별 기록</h2>
          <p v-if="!logSessions.length" class="muted">저장된 기록이 없어요.</p>
          <button v-for="item in logSessions" :key="item.session_id" class="list-item" :class="{ selected: activeLog === item.session_id }"
            :aria-current="activeLog === item.session_id || undefined" @click="openLog(item.session_id)">
            <strong>{{ formatStamp(item.last_at) }}</strong><small>실행 {{ item.run_count }}회 · 이벤트 {{ item.event_count }}건</small>
            <small>{{ item.session_id.slice(0, 8) }}</small>
          </button>
        </section>
        <section v-if="activeLog" class="log-detail">
          <div class="panel-title log-title"><h2>실행 기록 상세</h2><button class="button outline" @click="confirmation = 'logs'">기록 삭제</button></div>
          <EventList :events="logEvents" full />
        </section>
        <p v-else-if="logSessions.length" class="library-instruction">확인할 대화를 선택해 주세요.</p>
      </div>
    </section>

    <dialog v-if="sharedId" ref="sharedDialog" id="received-dialog" class="terminal-window terminal-library invitation-dialog received-dialog"
      aria-labelledby="received-title" @close="mainPage?.focus({ preventScroll: true })">
      <div class="invitation-toolbar">
        <TerminalBar>
          <h2 id="received-title" tabindex="-1" autofocus>받은 크리스마스 초대장</h2>
          <template #actions>
            <button class="quiet dialog-close" type="button" @click="sharedDialog?.close()">닫기</button>
          </template>
        </TerminalBar>
      </div>
      <Invitation v-if="sharedPlan" :plan="sharedPlan" />
      <p v-else class="library-instruction" role="status">{{ sharedError || '초대장을 불러오는 중…' }}</p>
    </dialog>

    <div v-if="feedback || error || confirmation" class="feedback-stack" aria-live="polite">
      <p v-if="feedback" class="notice">{{ feedback }}</p>
      <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
      <div v-if="confirmation" class="notice warning">
        <strong>{{ confirmation === 'plan' ? '이 초대장을 삭제할까요?' : '이 대화의 실행 기록을 삭제할까요?' }}</strong>
        <div class="actions"><button class="button primary" @click="confirmDelete">삭제 확인</button>
          <button class="button outline" @click="confirmation = null">취소</button></div>
      </div>
    </div>
  </main>
</template>
