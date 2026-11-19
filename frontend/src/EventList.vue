<script setup>
import { formatStamp } from './api'
defineProps({ events: { type: Array, required: true }, full: Boolean })
const stages = { analysis: '요청 분석', plan: '작업 계획', execute: 'Tool 실행', judge: '제약 판단', replan: '재계획', respond: '응답 생성' }
const labels = { stage_started: '시작', stage_finished: '완료', tool_requested: '호출', tool_completed: '응답', tool_reused: '재사용', decision_made: '판단', replan_requested: '대안 탐색', run_completed: '실행 완료', run_failed: '실행 실패' }
</script>

<template>
  <p v-if="!events.length" class="muted">아직 실행 기록이 없어요.</p>
  <ol v-else class="event-list">
    <li v-for="event in events" :key="event.event_id" :class="{ 'event-accent': event.event_type === 'replan_requested' || event.error_code }">
      <span class="event-index">{{ event.sequence }}</span>
      <div><strong>{{ event.tool_name || stages[event.stage] || '플래너' }} · {{ labels[event.event_type] || event.event_type }}</strong>
        <small v-if="event.reason">{{ event.reason }}</small><small v-if="event.error_code">{{ event.error_code }}</small>
        <small v-if="full">{{ formatStamp(event.timestamp) }}</small>
        <details v-if="full && (event.sanitized_input || event.sanitized_output)">
          <summary>호출 데이터</summary><pre>{{ JSON.stringify(event.sanitized_input || event.sanitized_output, null, 2) }}</pre>
        </details>
      </div><span v-if="event.duration_ms != null" class="event-time">{{ event.duration_ms }}ms</span>
    </li>
  </ol>
</template>
