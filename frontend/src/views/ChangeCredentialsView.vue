<template>
  <div class="overlay">
    <div class="modal">
      <div class="icon">🔐</div>
      <h1>처음 로그인하셨네요!</h1>
      <p class="lead">
        보안을 위해 <strong>아이디와 비밀번호를 변경</strong>해 주세요.<br />
        변경 후에는 새 정보로 로그인하게 됩니다.
      </p>

      <form @submit.prevent="submit">
        <label class="field">
          <span>새 아이디</span>
          <input v-model.trim="newUsername" type="text" autocomplete="username"
                 placeholder="4자 이상" />
          <small class="hint">현재: {{ currentUsername }} · 그대로 쓰려면 변경하지 않아도 됩니다</small>
        </label>

        <label class="field">
          <span>현재 비밀번호</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password"
                 placeholder="발급받은 임시 비밀번호" required
                 @keydown="onKey" @keyup="onKey" @blur="reset" />
        </label>

        <label class="field">
          <span>새 비밀번호</span>
          <input v-model="newPassword" type="password" autocomplete="new-password"
                 placeholder="6자 이상" required
                 @keydown="onKey" @keyup="onKey" @blur="reset" />
        </label>

        <label class="field">
          <span>새 비밀번호 확인</span>
          <input v-model="confirmPassword" type="password" autocomplete="new-password"
                 placeholder="한 번 더 입력" required
                 @keydown="onKey" @keyup="onKey" @blur="reset" />
        </label>

        <p v-if="capsOn" class="caps-warn">⇪ Caps Lock이 켜져 있어요 — 비밀번호가 대문자로 입력됩니다</p>

        <p v-if="error" class="err">{{ error }}</p>

        <button class="btn-primary" type="submit" :disabled="!valid || busy">
          {{ busy ? '변경 중…' : '변경하고 시작하기' }}
        </button>
      </form>

      <button class="btn-text" @click="logout">다른 계정으로 로그인</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCapsLock } from '@/composables/useCapsLock'

const { capsOn, onKey, reset } = useCapsLock()
const router = useRouter()
const auth = useAuthStore()

const currentUsername = computed(() => auth.user?.username || '')
const newUsername = ref('')
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const busy = ref(false)
const error = ref('')

onMounted(() => { newUsername.value = currentUsername.value })

const valid = computed(() =>
  newUsername.value.length >= 4 &&
  currentPassword.value.length > 0 &&
  newPassword.value.length >= 6 &&
  newPassword.value === confirmPassword.value)

async function submit() {
  error.value = ''
  if (newPassword.value !== confirmPassword.value) {
    error.value = '새 비밀번호가 서로 다릅니다.'; return
  }
  busy.value = true
  try {
    const user = await auth.changeCredentials({
      username: currentUsername.value,
      current_password: currentPassword.value,
      new_username: newUsername.value,
      new_password: newPassword.value,
    })
    router.push(user.role === 'admin' ? '/admin' : '/student')
  } catch (e: any) {
    const d = e?.response?.data?.detail
    error.value = typeof d === 'string' ? d
      : Array.isArray(d) ? d.map((x: any) => x.msg).join(', ')
      : '변경에 실패했습니다. 다시 시도해 주세요.'
  } finally { busy.value = false }
}

function logout() { auth.logout(); router.push('/login') }
</script>

<style scoped>
.overlay {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--mint-light) 0%, var(--gray-light) 100%); padding: 2rem;
}
.modal {
  background: var(--white); border-radius: var(--radius); box-shadow: var(--shadow-hover);
  padding: 2.5rem; width: 100%; max-width: 460px;
  display: flex; flex-direction: column; align-items: center; gap: 0.9rem;
}
.icon { font-size: 3rem; }
h1 { font-size: 1.35rem; font-weight: 900; color: var(--navy); text-align: center; }
.lead { color: var(--gray); text-align: center; line-height: 1.6; font-size: 0.95rem; }
form { width: 100%; display: flex; flex-direction: column; gap: 1rem; margin-top: 0.5rem; }
.field { display: flex; flex-direction: column; gap: 0.35rem; }
.field > span { font-weight: 800; font-size: 0.9rem; color: var(--navy); }
.field input {
  border: 2px solid #e8ecf0; border-radius: var(--radius-sm);
  padding: 0.8rem 1rem; font-size: 1rem; font-weight: 600; color: var(--navy); outline: none;
  transition: border-color 0.15s;
}
.field input:focus { border-color: var(--mint); }
.hint { color: var(--gray); font-size: 0.78rem; font-weight: 600; }
.caps-warn {
  font-size: 0.82rem; font-weight: 800; color: #b8860b;
  background: #fff8dd; padding: 0.55rem 0.8rem; border-radius: var(--radius-sm); text-align: center;
}
.err { color: var(--coral); font-weight: 700; font-size: 0.9rem; text-align: center; }
.btn-primary {
  background: var(--mint); color: white; border: none; padding: 0.9rem 1rem;
  border-radius: 99px; font-size: 1rem; font-weight: 800; transition: all 0.2s;
}
.btn-primary:hover:not(:disabled) { background: var(--mint-dark); transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-text { background: none; border: none; color: var(--gray); font-weight: 700; font-size: 0.85rem; text-decoration: underline; }
</style>
