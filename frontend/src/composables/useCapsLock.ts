import { ref } from 'vue'

/**
 * Caps Lock 상태 감지.
 *
 * 비밀번호 입력은 글자가 가려져 대문자 고정 여부를 알 수 없어 로그인 실패의
 * 흔한 원인이 된다. 키 이벤트의 getModifierState로 감지해 안내한다.
 *
 * 사용:
 *   const { capsOn, onKey, reset } = useCapsLock()
 *   <input @keydown="onKey" @keyup="onKey" @blur="reset" />
 *   <p v-if="capsOn">Caps Lock이 켜져 있어요</p>
 */
export function useCapsLock() {
  const capsOn = ref(false)

  function onKey(e: KeyboardEvent) {
    if (typeof e.getModifierState === 'function') {
      capsOn.value = e.getModifierState('CapsLock')
    }
  }

  // 포커스가 빠지면 경고를 숨긴다 (해당 입력과 무관한 상태 노출 방지)
  function reset() {
    capsOn.value = false
  }

  return { capsOn, onKey, reset }
}
