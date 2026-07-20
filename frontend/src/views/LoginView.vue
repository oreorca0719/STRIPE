<template>
  <div class="login-page">
    <div class="login-card">
      <div class="card-header">
        <div class="logo">📚 STRIPE</div>
        <h1>다시 만나서 반가워요!</h1>
        <p>로그인하고 오늘의 독서 여정을 시작해봐요 🌟</p>
      </div>

      <div v-if="expired" class="notice">
        <span class="notice-icon">⏰</span>
        <div>
          <strong>로그인 시간이 다 됐어요</strong>
          <p>다시 로그인하면 이어서 할 수 있어요. 하던 진단은 저장돼 있어요!</p>
        </div>
      </div>

      <form @submit.prevent="handleLogin" class="form">
        <div class="field">
          <label>아이디</label>
          <input v-model="form.username" type="text" placeholder="아이디를 입력하세요" required />
        </div>
        <div class="field">
          <label>비밀번호</label>
          <input v-model="form.password" type="password" placeholder="비밀번호를 입력하세요" required
                 @keydown="onKey" @keyup="onKey" @blur="reset" />
          <p v-if="capsOn" class="caps-warn">⇪ Caps Lock이 켜져 있어요</p>
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '로그인 중...' : '로그인 하기 🚀' }}
        </button>
      </form>

      <div class="footer">
        <span>아직 계정이 없나요?</span>
        <RouterLink to="/register">회원가입</RouterLink>
      </div>
    </div>

    <div class="deco deco-1">⭐</div>
    <div class="deco deco-2">📖</div>
    <div class="deco deco-3">✨</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCapsLock } from '@/composables/useCapsLock'

const { capsOn, onKey, reset } = useCapsLock()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

// 401 인터셉터가 토큰 만료로 돌려보낸 경우. 아동에게 "왜 튕겼는지"를 알려준다.
const expired = computed(() => route.query.reason === 'expired')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    const user = await auth.login(form.value.username, form.value.password)
    // 만료로 튕기기 전 있던 화면이 있으면 그리로 되돌린다.
    // 쿼리는 조작될 수 있으므로 내부 절대경로만 허용한다(`//`로 시작하는 외부 URL 차단).
    const from = route.query.from
    const safeFrom =
      typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') &&
      !from.startsWith('/login')
        ? from
        : null

    if (safeFrom) {
      router.replace(safeFrom)
    } else if (user.role === 'admin') {
      router.push('/admin')
    } else if (user.role === 'student') {
      router.push('/student')
    } else {
      router.push('/student')
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || '아이디 또는 비밀번호를 확인해주세요.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #E8FAF9 0%, #FFF9E6 100%);
  position: relative;
  overflow: hidden;
}
.login-card {
  background: var(--white);
  border-radius: var(--radius);
  padding: 3rem 2.5rem;
  width: 100%;
  max-width: 420px;
  box-shadow: var(--shadow);
  position: relative;
  z-index: 1;
}
.card-header { text-align: center; margin-bottom: 2rem; }
.logo { font-size: 1.8rem; font-weight: 900; color: var(--mint-dark); margin-bottom: 1rem; }
h1 { font-size: 1.4rem; font-weight: 800; color: var(--navy); margin-bottom: 0.5rem; }
p { color: var(--gray); font-size: 0.95rem; }
.form { display: flex; flex-direction: column; gap: 1.2rem; }
.field { display: flex; flex-direction: column; gap: 0.4rem; }
label { font-weight: 700; font-size: 0.9rem; color: var(--navy); }
input {
  padding: 0.8rem 1rem;
  border: 2px solid #e8ecf0;
  border-radius: var(--radius-sm);
  font-size: 1rem;
  transition: border-color 0.2s;
  outline: none;
}
input:focus { border-color: var(--mint); }
.caps-warn {
  margin-top: 0.4rem;
  font-size: 0.8rem;
  font-weight: 800;
  color: #b8860b;
  background: #fff8dd;
  padding: 0.4rem 0.7rem;
  border-radius: var(--radius-sm);
}

.notice {
  display: flex; align-items: flex-start; gap: 0.7rem;
  background: rgba(255, 193, 94, 0.12);
  border: 1px solid rgba(255, 193, 94, 0.35);
  border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 1.2rem;
  text-align: left;
}
.notice-icon { font-size: 1.2rem; line-height: 1.3; }
.notice strong { display: block; color: #E8A33D; font-size: 0.92rem; font-weight: 800; }
.notice p { color: #B08535; font-size: 0.82rem; margin-top: 0.2rem; line-height: 1.5; }

.error-msg {
  background: #fff0f0;
  color: var(--coral);
  padding: 0.7rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  font-weight: 600;
}
.submit-btn {
  background: var(--mint);
  color: var(--white);
  border: none;
  padding: 1rem;
  border-radius: var(--radius-sm);
  font-size: 1rem;
  font-weight: 800;
  transition: all 0.2s;
  margin-top: 0.5rem;
}
.submit-btn:hover:not(:disabled) {
  background: var(--mint-dark);
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.footer {
  text-align: center; margin-top: 1.5rem;
  font-size: 0.9rem; color: var(--gray);
  display: flex; gap: 0.5rem; justify-content: center;
}
.footer a { color: var(--mint-dark); font-weight: 700; text-decoration: none; }
.footer a:hover { text-decoration: underline; }
.deco { position: absolute; font-size: 3rem; opacity: 0.15; animation: float 4s ease-in-out infinite; }
.deco-1 { top: 10%; left: 8%; animation-delay: 0s; }
.deco-2 { bottom: 15%; right: 8%; animation-delay: 1.5s; }
.deco-3 { top: 60%; left: 5%; animation-delay: 0.8s; font-size: 2rem; }
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}
</style>
