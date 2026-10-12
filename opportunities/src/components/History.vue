<script setup>
import axios from 'axios'
import { ref } from 'vue'

import { DOMAIN } from '../utils.js'

const rows = ref([])
const users = ref([])
const projects = ref([])
const filterUser = ref('')
const filterProject = ref('')
const expanded = ref(null)

async function fetchFilters() {
  const [u, p] = await Promise.all([
    axios.get(DOMAIN.concat('/api/users')),
    axios.get(DOMAIN.concat('/api/projects')),
  ])
  users.value = u.data
  projects.value = p.data.projects
}

async function fetchHistory() {
  const params = {}
  if (filterUser.value) params.user = filterUser.value
  if (filterProject.value) params.project = filterProject.value
  const res = await axios.get(DOMAIN.concat('/api/history'), { params })
  rows.value = res.data
}

function toggle(id) {
  expanded.value = expanded.value === id ? null : id
}

// Standard project display string: "number name — category" (AT/EV are special).
function projectDisplay(row) {
  if (row.category === 'AT') return `AT — ${row.project_id || '(activity)'}`
  if (row.category === 'EV') return 'EV — Event'
  if (!row.project_id) return row.category || '—'
  const name = row.project_name ? ` ${row.project_name}` : ''
  return `${row.project_id}${name} — ${row.category}`
}

// Human-readable value for a changed field.
function fmt(v) {
  if (v === null || v === undefined || v === '') return '(empty)'
  if (v === true) return 'Yes'
  if (v === false) return 'No'
  return v
}

fetchFilters()
fetchHistory()
</script>

<template>
  <div class="navigation">
    <RouterLink to="/">Home</RouterLink>
  </div>
  <h1>Opportunity History</h1>

  <div class="filters">
    <label>
      Editor
      <select v-model="filterUser" @change="fetchHistory">
        <option value="">Anyone</option>
        <option v-for="u in users" :key="u.id" :value="u.id">{{ u.email }}</option>
      </select>
    </label>
    <label>
      Project
      <select v-model="filterProject" @change="fetchHistory">
        <option value="">Any project</option>
        <option v-for="p in projects" :key="p.project_id" :value="p.project_id">
          {{ p.project_id }} — {{ p.name }}
        </option>
      </select>
    </label>
  </div>

  <table class="history">
    <thead>
      <tr>
        <th>When</th>
        <th>Editor</th>
        <th>Action</th>
        <th>Opportunity</th>
        <th>Project / Category</th>
        <th>Changes</th>
      </tr>
    </thead>
    <tbody>
      <template v-for="row in rows" :key="row.id">
        <tr :class="'action-' + row.action">
          <td>{{ row.changed_at }}</td>
          <td>{{ row.email || '—' }}</td>
          <td><span class="badge">{{ row.action }}</span></td>
          <td>{{ row.title || '—' }}</td>
          <td>{{ projectDisplay(row) }}</td>
          <td>
            <template v-if="row.action === 'update'">
              <button v-if="row.changes.length" class="link" @click="toggle(row.id)">
                {{ expanded === row.id ? 'hide' : `${row.changes.length} field${row.changes.length > 1 ? 's' : ''}` }}
              </button>
              <span v-else class="muted">no field changes</span>
            </template>
            <span v-else-if="row.action === 'create'" class="muted">created</span>
            <span v-else-if="row.action === 'delete'" class="muted">deleted</span>
          </td>
        </tr>
        <tr v-if="expanded === row.id" class="changes-row">
          <td colspan="6">
            <table class="changes">
              <thead><tr><th>Field</th><th>Old</th><th>New</th></tr></thead>
              <tbody>
                <tr v-for="c in row.changes" :key="c.field">
                  <td>{{ c.label }}</td>
                  <td class="old">{{ fmt(c.old) }}</td>
                  <td class="new">{{ fmt(c.new) }}</td>
                </tr>
              </tbody>
            </table>
          </td>
        </tr>
      </template>
      <tr v-if="!rows.length"><td colspan="6"><i>No history matches these filters.</i></td></tr>
    </tbody>
  </table>
</template>

<style scoped>
  .navigation { text-align: right; }
  .filters { display: flex; gap: 20px; margin: 16px 0; flex-wrap: wrap; }
  .filters label { display: flex; flex-direction: column; font-size: .85em; gap: 4px; }
  .filters select { height: 36px; padding: 0 8px; min-width: 220px; }
  .history { border-collapse: collapse; width: 100%; }
  .history th, .history td { border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; vertical-align: top; }
  .history th { background: #f3f4f6; }
  .badge { font-size: .8em; font-weight: 600; text-transform: uppercase; }
  .action-delete .badge { color: #b91c1c; }
  .action-create .badge { color: #047857; }
  .action-update .badge { color: #1d4ed8; }
  .link { border: none; background: none; color: #2563eb; cursor: pointer; padding: 0; text-decoration: underline; }
  .muted { color: #9ca3af; font-size: .85em; }
  .changes-row td { background: #f9fafb; }
  .changes { border-collapse: collapse; width: 100%; max-width: 900px; }
  .changes th, .changes td { border: 1px solid #e5e7eb; padding: 4px 8px; text-align: left; font-size: .9em; vertical-align: top; }
  .changes .old { color: #b91c1c; text-decoration: line-through; }
  .changes .new { color: #047857; }
</style>
