<script setup>
import axios from 'axios'
import { ref, computed } from 'vue'

import User from './User.vue'
import { DOMAIN } from '../utils.js'
import { sortUsers } from '../permissions.js'

const users = ref([])
const search = ref('')
const sortKey = ref('email')
const sortDir = ref('asc')

const filteredUsers = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return users.value
  return users.value.filter(u => (u.email || '').toLowerCase().includes(q))
})

function setSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

function sortArrow(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const sortedUsers = computed(() => sortUsers(filteredUsers.value, sortKey.value, sortDir.value))

async function fetchUsers() {
  const res = await axios.get(DOMAIN.concat(`/api/users`))
  users.value = await res.data
}


fetchUsers()

</script>

<template>
  <div class="navigation">
    <RouterLink to="/">Home</RouterLink>
  </div>
  <h1>Users</h1>
  <div class="search">
    <input v-model="search" type="search" placeholder="Filter by email…" />
  </div>
  <table class="users">
    <thead>
      <tr>
        <th><button class="sort" @click="setSort('email')">Email{{ sortArrow('email') }}</button></th>
        <th><button class="sort" @click="setSort('type')">Type{{ sortArrow('type') }}</button></th>
        <th><button class="sort" @click="setSort('last_login')">Last login{{ sortArrow('last_login') }}</button></th>
        <th><button class="sort" @click="setSort('projects')">Assigned project / category{{ sortArrow('projects') }}</button></th>
        <th>Manage</th>
      </tr>
    </thead>
    <tbody>
      <User v-for="user in sortedUsers" :key="user.id" :user="user" />
      <tr v-if="!sortedUsers.length"><td colspan="5"><i>No users match “{{ search }}”.</i></td></tr>
    </tbody>
  </table>
</template>

<style scoped>
  .navigation {
    text-align: right;
  }
  .users {
    border-collapse: collapse;
    width: 100%;
  }
  .users th, .users :deep(td) {
    border: 1px solid #d1d5db;
    padding: 6px 10px;
    text-align: left;
    vertical-align: top;
  }
  .users th { background: #f3f4f6; padding: 0; }
  .sort {
    width: 100%;
    border: none;
    background: none;
    font: inherit;
    font-weight: bold;
    text-align: left;
    padding: 6px 10px;
    cursor: pointer;
    white-space: nowrap;
  }
  .sort:hover { background: #e5e7eb; }
  .search { margin: 12px 0; }
  .search input { width: 100%; max-width: 360px; height: 36px; padding: 0 10px; box-sizing: border-box; }
</style>
