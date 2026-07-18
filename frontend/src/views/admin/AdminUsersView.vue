<template>
  <AdminLayout @logout="handleLogout">
    <template #title>사용자 관리</template>

    <div class="users-page">
      <!-- 탭 + 검색 -->
      <div class="toolbar">
        <div class="tabs">
          <button
            v-for="tab in tabs" :key="tab.value"
            class="tab" :class="{ active: activeTab === tab.value }"
            @click="activeTab = tab.value; loadUsers()"
          >
            {{ tab.icon }} {{ tab.label }}
            <span class="tab-count">{{ counts[tab.value] ?? 0 }}</span>
          </button>
        </div>
        <div class="search-bar">
          <input v-model="search" placeholder="이름 또는 아이디 검색..." />
        </div>
      </div>

      <!-- 테이블 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>아이디</th>
              <th>이름</th>
              <th v-if="activeTab === 'student'">학년</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="5">
                <div class="empty-state"><span>⏳</span><span>불러오는 중...</span></div>
              </td>
            </tr>
            <tr v-else-if="filteredUsers.length === 0">
              <td colspan="5">
                <div class="empty-state"><span>👤</span><span>사용자가 없습니다</span></div>
              </td>
            </tr>
            <tr v-for="user in filteredUsers" :key="user.id" class="data-row">
              <td class="td-id">{{ user.id }}</td>
              <td class="td-username">{{ user.username }}</td>
              <td class="td-name">{{ user.name }}</td>
              <td v-if="activeTab === 'student'" class="td-grade">{{ gradeLabel(user.grade) }}</td>
              <td>
                <span class="status-badge" :class="user.is_active ? 'active' : 'inactive'">
                  {{ user.is_active ? '활성' : '비활성' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 페이지네이션 -->
      <div class="pagination">
        <span class="page-info">전체 {{ filteredUsers.length }}명</span>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import AdminLayout from '@/components/admin/AdminLayout.vue'

const router = useRouter()

const activeTab = ref('student')
const search = ref('')
const users = ref<any[]>([])
const counts = ref<Record<string, number>>({})
const loading = ref(false)

const tabs = [
  { value: 'student', label: '학생', icon: '👨‍🎓' },
  { value: 'parent', label: '학부모', icon: '👨‍👩‍👧' },
  { value: 'teacher', label: '교사', icon: '👩‍🏫' },
]

const gradeMap: Record<string, string> = {
  elem1: '초등 1학년', elem2: '초등 2학년', elem3: '초등 3학년',
  elem4: '초등 4학년', elem5: '초등 5학년', elem6: '초등 6학년',
  mid1: '중등 1학년',
}

function gradeLabel(grade: string | null) {
  return grade ? gradeMap[grade] ?? grade : '-'
}

const filteredUsers = computed(() => {
  if (!search.value) return users.value
  const q = search.value.toLowerCase()
  return users.value.filter(u =>
    u.username.toLowerCase().includes(q) || u.name.toLowerCase().includes(q)
  )
})

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.get(`/api/admin/users`, {
      params: { role: activeTab.value }
    })
    users.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadCounts() {
  try {
    const res = await api.get(`/api/admin/users/count`)
    counts.value = res.data
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadUsers()
  loadCounts()
})

function handleLogout() { router.push('/login') }
</script>

<style scoped>
.users-page { display: flex; flex-direction: column; gap: 1.2rem; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px; padding: 1rem 1.5rem;
}
.tabs { display: flex; gap: 0.4rem; }
.tab {
  background: none; border: 1px solid #2a2d3e; color: #666;
  padding: 0.5rem 1.2rem; border-radius: 8px;
  font-size: 0.85rem; font-weight: 700; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 0.5rem;
}
.tab.active { background: rgba(78,205,196,0.15); border-color: #4ECDC4; color: #4ECDC4; }
.tab:hover:not(.active) { border-color: #444; color: #aaa; }
.tab-count {
  background: rgba(255,255,255,0.1); border-radius: 99px;
  padding: 0.1rem 0.5rem; font-size: 0.75rem;
}

.search-bar input {
  background: #252836; border: 1px solid #2a2d3e; color: #fff;
  padding: 0.6rem 1.2rem; border-radius: 8px; font-size: 0.9rem;
  width: 280px; outline: none; font-family: 'Nunito', sans-serif;
}
.search-bar input:focus { border-color: #4ECDC4; }
.search-bar input::placeholder { color: #555; }

.table-wrap {
  background: #1a1d27; border: 1px solid #2a2d3e;
  border-radius: 16px; overflow: hidden;
}
.data-table { width: 100%; border-collapse: collapse; }
.data-table th {
  text-align: left; padding: 1rem 1.5rem;
  font-size: 0.75rem; font-weight: 800; color: #555;
  text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 1px solid #2a2d3e;
}
.data-row td { padding: 0.9rem 1.5rem; border-bottom: 1px solid #1e2130; color: #aaa; font-size: 0.9rem; }
.data-row:hover td { background: #1e2130; }
.data-row:last-child td { border-bottom: none; }
.td-id { color: #555; font-size: 0.8rem; }
.td-username { color: #4ECDC4; font-weight: 700; }
.td-name { color: #fff; font-weight: 600; }
.td-grade { color: #888; font-size: 0.85rem; }

.status-badge {
  font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.7rem; border-radius: 99px;
}
.active { background: rgba(78,205,196,0.15); color: #4ECDC4; }
.inactive { background: rgba(255,107,107,0.15); color: #FF6B6B; }

.empty-state {
  display: flex; align-items: center; gap: 0.7rem; justify-content: center;
  padding: 3rem; color: #555; font-size: 0.9rem;
}

.pagination {
  display: flex; align-items: center; justify-content: center;
}
.page-info { color: #555; font-size: 0.85rem; font-weight: 700; }
</style>
