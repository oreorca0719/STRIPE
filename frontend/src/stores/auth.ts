import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const API = import.meta.env.VITE_API_BASE_URL || ''

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<any | null>(JSON.parse(localStorage.getItem('user') || 'null'))

  async function login(username: string, password: string) {
    const res = await axios.post(`${API}/api/auth/login`, { username, password })
    token.value = res.data.access_token
    user.value = res.data.user
    localStorage.setItem('token', token.value!)
    localStorage.setItem('user', JSON.stringify(user.value))
    return res.data.user
  }

  async function register(data: {
    username: string
    password: string
    name: string
    role: string
    grade?: string
  }) {
    const res = await axios.post(`${API}/api/auth/register`, data)
    return res.data
  }

  async function changeCredentials(data: {
    username: string
    current_password: string
    new_username?: string
    new_password: string
  }) {
    const res = await axios.post(`${API}/api/auth/change-credentials`, data)
    token.value = res.data.access_token
    user.value = res.data.user
    localStorage.setItem('token', token.value!)
    localStorage.setItem('user', JSON.stringify(user.value))
    return res.data.user
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function isLoggedIn() {
    return !!token.value
  }

  return { token, user, login, register, changeCredentials, logout, isLoggedIn }
})
