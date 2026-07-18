<template>
  <div class="register-page">
    <div class="register-card">
      <div class="card-header">
        <div class="logo">📚 STRIPE</div>
        <h1>함께 시작해요!</h1>
        <p>STRIPE와 함께 독서 능력을 키워봐요 🌱</p>
      </div>

      <form @submit.prevent="handleRegister" class="form">
        <div class="field">
          <label>이름</label>
          <input v-model="form.name" type="text" placeholder="이름을 입력하세요" required />
        </div>
        <div class="field">
          <label>아이디</label>
          <input v-model="form.username" type="text" placeholder="아이디를 입력하세요 (4자 이상)" required />
        </div>
        <div class="field">
          <label>학년</label>
          <select v-model="form.grade">
            <option value="">학년을 선택하세요</option>
            <option v-for="g in grades" :key="g.value" :value="g.value">{{ g.label }}</option>
          </select>
        </div>
        <div class="field">
          <label>비밀번호</label>
          <input v-model="form.password" type="password" placeholder="비밀번호를 입력하세요 (6자 이상)" required
                 @keydown="onKey" @keyup="onKey" @blur="reset" />
        </div>
        <div class="field">
          <label>비밀번호 확인</label>
          <input v-model="form.passwordConfirm" type="password" placeholder="비밀번호를 다시 입력하세요" required
                 @keydown="onKey" @keyup="onKey" @blur="reset" />
          <p v-if="capsOn" class="caps-warn">⇪ Caps Lock이 켜져 있어요</p>
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>
        <div v-if="success" class="success-msg">{{ success }}</div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '가입 중...' : '회원가입 하기 🎉' }}
        </button>
      </form>

      <div class="footer">
        <span>이미 계정이 있나요?</span>
        <RouterLink to="/login">로그인</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCapsLock } from '@/composables/useCapsLock'

const { capsOn, onKey, reset } = useCapsLock()

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const success = ref('')

const form = ref({
  name: '', username: '', grade: '', password: '', passwordConfirm: ''
})

// 서비스 대상은 초4~중1 (PM 결정 2026-07-18). 콘텐츠 풀이 G4_G6·G7 두 학년군으로만
// 구성돼 있어 대상 밖 학년은 맞는 난도의 지문이 없다. 서버도 같은 기준으로 검증한다.
const grades = [
  { value: 'elem4', label: '초등학교 4학년' },
  { value: 'elem5', label: '초등학교 5학년' },
  { value: 'elem6', label: '초등학교 6학년' },
  { value: 'mid1',  label: '중학교 1학년' },
]

async function handleRegister() {
  if (form.value.password !== form.value.passwordConfirm) {
    error.value = '비밀번호가 일치하지 않아요!'; return
  }
  loading.value = true; error.value = ''; success.value = ''
  try {
    await auth.register({
      username: form.value.username,
      password: form.value.password,
      name: form.value.name,
      role: 'student',
      grade: form.value.grade || undefined,
    })
    success.value = '가입 완료! 로그인 페이지로 이동합니다.'
    setTimeout(() => router.push('/login'), 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || '회원가입 중 오류가 발생했어요. 다시 시도해주세요.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #FFF9E6 0%, #E8FAF9 100%);
  padding: 2rem 1rem;
}
.register-card {
  background: var(--white);
  border-radius: var(--radius);
  padding: 3rem 2.5rem;
  width: 100%;
  max-width: 440px;
  box-shadow: var(--shadow);
}
.card-header { text-align: center; margin-bottom: 2rem; }
.logo { font-size: 1.8rem; font-weight: 900; color: var(--mint-dark); margin-bottom: 1rem; }
h1 { font-size: 1.4rem; font-weight: 800; color: var(--navy); margin-bottom: 0.5rem; }
p { color: var(--gray); font-size: 0.95rem; }
.form { display: flex; flex-direction: column; gap: 1rem; }
.field { display: flex; flex-direction: column; gap: 0.4rem; }
label { font-weight: 700; font-size: 0.9rem; color: var(--navy); }
input, select {
  padding: 0.8rem 1rem;
  border: 2px solid #e8ecf0;
  border-radius: var(--radius-sm);
  font-size: 1rem;
  transition: border-color 0.2s;
  outline: none;
  font-family: 'Nunito', sans-serif;
  background: white;
}
input:focus, select:focus { border-color: var(--mint); }
.caps-warn {
  margin-top: 0.4rem; font-size: 0.8rem; font-weight: 800;
  color: #b8860b; background: #fff8dd; padding: 0.4rem 0.7rem; border-radius: var(--radius-sm);
}

.error-msg {
  background: #fff0f0; color: var(--coral);
  padding: 0.7rem 1rem; border-radius: var(--radius-sm);
  font-size: 0.9rem; font-weight: 600;
}
.success-msg {
  background: #f0fff9; color: var(--mint-dark);
  padding: 0.7rem 1rem; border-radius: var(--radius-sm);
  font-size: 0.9rem; font-weight: 600;
}
.submit-btn {
  background: var(--yellow); color: var(--navy); border: none;
  padding: 1rem; border-radius: var(--radius-sm);
  font-size: 1rem; font-weight: 800; transition: all 0.2s; margin-top: 0.5rem;
}
.submit-btn:hover:not(:disabled) {
  background: var(--yellow-dark);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(255,230,109,0.4);
}
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.footer {
  text-align: center; margin-top: 1.5rem;
  font-size: 0.9rem; color: var(--gray);
  display: flex; gap: 0.5rem; justify-content: center;
}
.footer a { color: var(--mint-dark); font-weight: 700; text-decoration: none; }
.footer a:hover { text-decoration: underline; }
</style>
