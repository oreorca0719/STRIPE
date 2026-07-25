<template>
  <div class="books-page">
    <NavBar @logout="handleLogout" />

    <main class="main">
      <div class="head">
        <button class="back-btn" @click="router.push('/student')">← 홈으로</button>
        <h1>📖 나에게 맞는 책</h1>
      </div>

      <p v-if="loading" class="msg">찾아보는 중이에요…</p>

      <p v-else-if="error" class="msg msg--error">
        추천을 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.
      </p>

      <!-- 진단 전 -->
      <div v-else-if="data?.reason === 'no_diagnosis' || data?.reason === 'no_profile'"
           class="empty">
        <div class="empty-icon">🔍</div>
        <h2>먼저 진단을 해볼까요?</h2>
        <p>어떤 책이 잘 맞는지 알려면 읽기 진단이 필요해요.</p>
        <button class="cta" @click="router.push('/student/diagnosis')">진단 시작하기</button>
      </div>

      <!-- 카탈로그가 아직 비어 있음 -->
      <div v-else-if="data?.catalog_empty" class="empty">
        <div class="empty-icon">📚</div>
        <h2>책을 고르고 있어요</h2>
        <p>
          너에게 맞는 책 목록을 준비하는 중이에요.<br />
          곧 만나볼 수 있어요!
        </p>
        <div v-if="basis" class="basis basis--muted">
          <span class="basis-title">준비되면 이런 책을 찾아줄 거예요</span>
          <span>{{ basisText }}</span>
        </div>
      </div>

      <!-- 조건에 맞는 책이 없음 -->
      <div v-else-if="!data?.books?.length" class="empty">
        <div class="empty-icon">🧐</div>
        <h2>딱 맞는 책을 아직 못 찾았어요</h2>
        <p>조건에 맞는 책이 준비되면 알려줄게요.</p>
      </div>

      <!-- 추천 목록 -->
      <template v-else>
        <div v-if="basis" class="basis">
          <span class="basis-title">이런 기준으로 골랐어요</span>
          <span>{{ basisText }}</span>
        </div>

        <div class="list">
          <article v-for="b in data.books" :key="b.id" class="book">
            <div class="cover" :class="{ 'cover--none': !b.cover_url }">
              <img v-if="b.cover_url" :src="b.cover_url" :alt="b.title" />
              <span v-else>📕</span>
            </div>

            <div class="body">
              <h3 class="title">{{ b.title }}</h3>
              <p class="meta">
                <span v-if="b.author">{{ b.author }}</span>
                <span v-if="b.publisher" class="dot">·</span>
                <span v-if="b.publisher">{{ b.publisher }}</span>
                <span v-if="b.page_count" class="dot">·</span>
                <span v-if="b.page_count">{{ b.page_count }}쪽</span>
              </p>
              <p v-if="b.description" class="desc">{{ b.description }}</p>

              <div class="tags">
                <span class="tag tag--level">{{ diffKo(b.difficulty) }}</span>
                <span class="tag">{{ b.genre === 'narrative' ? '이야기책' : '지식책' }}</span>
                <span v-for="t in b.matched_topics" :key="t" class="tag tag--match">
                  {{ topicKo(t) }} 좋아하잖아 ✨
                </span>
              </div>
            </div>
          </article>
        </div>

        <p class="foot-note">
          읽기 수준은 계속 자라요. 다음에 또 진단하면 새로운 책을 추천해줄게요.
        </p>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { api } from '@/api'

const router = useRouter()
const data = ref<any>(null)
const loading = ref(true)
const error = ref(false)

const DIFF_KO: Record<string, string> = { easy: '쉬운 책', normal: '알맞은 책', hard: '도전하는 책' }
function diffKo(d: string) { return DIFF_KO[d] || d }

// 지문 생성에 쓰는 B7 태그와 같은 taxonomy
const TOPIC_KO: Record<string, string> = {
  ANIMAL: '동물', FRIENDSHIP: '우정', ADVENTURE: '모험', FAMILY: '가족', FANTASY: '판타지',
  SCIENCE: '과학', NATURE: '자연', SPACE: '우주', HISTORY: '역사', DAILY: '일상',
}
function topicKo(t: string) { return TOPIC_KO[t] || t }

const basis = computed(() => data.value?.based_on)

// 왜 이 책들인지 아동이 알아볼 수 있게 풀어 쓴다. 근거 없이 목록만 주면
// '추천도서'와 다를 바 없다(§5-1 적합도서).
const basisText = computed(() => {
  const b = basis.value
  if (!b) return ''
  const levels = (b.difficulties || []).map((d: string) => diffKo(d)).join(', ')
  const topics = (b.interest_topics || []).map((t: string) => topicKo(t)).join(', ')
  const parts = [levels && `${levels} 위주`]
  if (topics) parts.push(`관심 주제는 ${topics}`)
  if (b.prefer_short) parts.push('끝까지 읽기 좋은 짧은 책 먼저')
  return parts.filter(Boolean).join(' · ')
})

async function load() {
  try {
    data.value = (await api.get('/api/diagnosis/my/books')).data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function handleLogout() { router.push('/login') }
onMounted(load)
</script>

<style scoped>
.books-page { min-height: 100vh; background: var(--gray-light); }
.main { max-width: 780px; margin: 0 auto; padding: 2rem; }

.head { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }
.head h1 { font-size: 1.5rem; font-weight: 900; color: var(--navy); }
.back-btn {
  background: var(--white); border: none; border-radius: 99px;
  padding: 0.5rem 1rem; font-weight: 700; color: var(--gray);
  cursor: pointer; box-shadow: var(--shadow); min-height: 44px;
}
.back-btn:hover { color: var(--navy); }

.msg { text-align: center; color: var(--gray); padding: 3rem 1rem; }
.msg--error { color: var(--coral); }

.empty {
  background: var(--white); border-radius: var(--radius);
  padding: 3rem 2rem; text-align: center; box-shadow: var(--shadow);
}
.empty-icon { font-size: 3rem; margin-bottom: 1rem; }
.empty h2 { font-size: 1.2rem; font-weight: 800; color: var(--navy); margin-bottom: 0.5rem; }
.empty p { color: var(--gray); line-height: 1.7; margin-bottom: 1.5rem; }
.cta {
  background: var(--mint); color: white; border: none; border-radius: 99px;
  padding: 0.8rem 2rem; font-weight: 800; font-size: 1rem; cursor: pointer; min-height: 56px;
}
.cta:hover { background: var(--mint-dark); }

.basis {
  background: #E8F8F7; border-radius: var(--radius-sm);
  padding: 0.9rem 1.1rem; margin-bottom: 1.2rem;
  display: flex; flex-direction: column; gap: 0.2rem;
}
.basis--muted { background: var(--gray-light); margin-top: 1rem; margin-bottom: 0; }
.basis-title { font-size: 0.78rem; font-weight: 800; color: var(--mint-dark); }
.basis span:last-child { font-size: 0.9rem; color: var(--navy); }

.list { display: flex; flex-direction: column; gap: 1rem; }
.book {
  display: flex; gap: 1.1rem; background: var(--white);
  border-radius: var(--radius-sm); padding: 1.1rem; box-shadow: var(--shadow);
}
.cover {
  width: 76px; height: 104px; flex-shrink: 0; border-radius: 6px;
  overflow: hidden; background: var(--gray-light);
  display: flex; align-items: center; justify-content: center; font-size: 2rem;
}
.cover img { width: 100%; height: 100%; object-fit: cover; }

.body { flex: 1; min-width: 0; }
.title { font-size: 1.05rem; font-weight: 800; color: var(--navy); margin-bottom: 0.3rem; }
.meta { font-size: 0.84rem; color: var(--gray); margin-bottom: 0.5rem; }
.meta .dot { margin: 0 0.35rem; }
.desc {
  font-size: 0.88rem; color: var(--gray); line-height: 1.6; margin-bottom: 0.6rem;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}

.tags { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.tag {
  font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem;
  border-radius: 99px; background: var(--gray-light); color: var(--gray);
}
.tag--level { background: var(--navy); color: white; }
.tag--match { background: #FFF3C4; color: #8A6D00; }

.foot-note { text-align: center; color: var(--gray); font-size: 0.85rem; padding: 1.5rem 0 0; }

@media (max-width: 560px) {
  .main { padding: 1rem; }
  .book { gap: 0.8rem; padding: 0.9rem; }
  .cover { width: 60px; height: 82px; }
}
</style>
