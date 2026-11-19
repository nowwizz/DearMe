<script setup>
import { computed, onMounted, ref } from 'vue'
import { invitationLink, prepareKakaoShare, sendKakaoInvitation } from './kakaoShare'

const props = defineProps({ entry: { type: Object, required: true } })
const link = computed(() => invitationLink(props.entry.id))
const loading = ref(true)
const feedback = ref('')
const showLink = ref(false)
const publicSite = window.location.protocol === 'https:' &&
  !['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
let kakaoShare

onMounted(async () => {
  try {
    if (publicSite) kakaoShare = await prepareKakaoShare()
  } catch {
    kakaoShare = undefined
  } finally {
    loading.value = false
  }
})

async function share() {
  feedback.value = ''
  if (!publicSite) {
    feedback.value = '카카오톡으로 보내려면 공개 HTTPS 사이트에서 초대장을 열어 주세요.'
    return
  }
  if (!kakaoShare) {
    feedback.value = kakaoShare === null ? '카카오 JavaScript 키를 설정해 주세요.' : '카카오톡 공유를 불러오지 못했어요.'
    return
  }
  try {
    await sendKakaoInvitation(kakaoShare, props.entry)
  } catch {
    feedback.value = '공유창을 열지 못했어요. 카카오 앱의 웹 도메인 설정을 확인해 주세요.'
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(link.value)
    feedback.value = '초대장 링크를 복사했어요.'
  } catch {
    showLink.value = true
    feedback.value = '아래 초대장 링크를 복사해 주세요.'
  }
}
</script>

<template>
  <div class="invitation-share">
    <div class="actions">
      <button type="button" class="button kakao-share" :disabled="loading" @click="share">카카오톡 공유</button>
      <button type="button" class="button outline" @click="copyLink">링크 복사</button>
    </div>
    <p v-if="feedback" class="muted" role="status">{{ feedback }}</p>
    <input v-if="showLink" :value="link" type="url" aria-label="초대장 링크" readonly @focus="$event.target.select()">
  </div>
</template>
