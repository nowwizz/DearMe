import { api } from './api'

const sdkUrl = 'https://t1.kakaocdn.net/kakao_js_sdk/2.8.5/kakao.min.js'
const sdkIntegrity = 'sha384-v6JKY3z4FUkWq21oZDHZe74YvuPk/WUrVLrDHTBojHXClOSa3iXy7sCXPY1jkFbj'
let setup

export function prepareKakaoShare() {
  setup ??= initialize().catch(error => {
    setup = undefined
    throw error
  })
  return setup
}

async function initialize() {
  const { kakao_js_key: key } = await api('/share-config')
  if (!key) return null
  if (!window.Kakao) {
    await new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = sdkUrl
      script.integrity = sdkIntegrity
      script.crossOrigin = 'anonymous'
      script.onload = resolve
      script.onerror = () => {
        script.remove()
        reject(new Error('카카오톡 공유를 불러오지 못했어요.'))
      }
      document.head.append(script)
    })
  }
  const kakao = window.Kakao
  if (!kakao.isInitialized()) kakao.init(key)
  return kakao.Share
}

export function invitationLink(id) {
  const url = new URL('/', window.location.origin)
  url.searchParams.set('invite', id)
  return url.href
}

export function sendKakaoInvitation(share, { id, title, date }) {
  const url = invitationLink(id)
  const link = { mobileWebUrl: url, webUrl: url }
  return share.sendDefault({
    objectType: 'feed',
    content: {
      title,
      description: [date, 'Dear. Me 크리스마스 초대장'].filter(Boolean).join(' · '),
      imageUrl: new URL('/invitation-share.png', url).href,
      link,
    },
    buttons: [{ title: '초대장 열기', link }],
  })
}
