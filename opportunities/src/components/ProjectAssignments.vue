<script setup>
import axios from 'axios'
import { ref, computed } from 'vue'

import { DOMAIN } from '../utils.js'

const assignments = ref([])   // {id, project_id, category, coordinator_id, email}
const users = ref([])
const projects = ref([])      // {project_id, name, categories:[], stale}
const err = ref(null)

const importSummary = ref(null)
const importing = ref(false)
const fileInput = ref(null)

// Add-assignment form
const addProjectId = ref('')
const addCategory = ref('')
const addCoordinatorId = ref('')

const coordinators = computed(() =>
  users.value.filter(u => u.project_coordinator || u.admin)
)

// One row per (project, category) combination — same shape as the dropdown.
const combos = computed(() =>
  projects.value.flatMap(p =>
    (p.categories || []).map(cat => ({
      project_id: p.project_id,
      name: p.name,
      category: cat,
      stale: p.stale,
    }))
  )
)

// Categories available for the currently-chosen project in the add form.
const addCategories = computed(() => {
  const p = projects.value.find(p => p.project_id === addProjectId.value)
  return p ? p.categories : []
})

function coordsFor(combo) {
  return assignments.value.filter(
    a => a.project_id === combo.project_id && a.category === combo.category
  )
}

async function fetchAll() {
  const [a, u, p] = await Promise.all([
    axios.get(DOMAIN.concat('/api/assignments')),
    axios.get(DOMAIN.concat('/api/users')),
    axios.get(DOMAIN.concat('/api/projects')),
  ])
  assignments.value = a.data
  users.value = u.data
  projects.value = p.data.projects
}

async function addAssignment() {
  err.value = null
  const res = await axios.post(DOMAIN.concat('/api/assignments'), {
    project_id: addProjectId.value,
    category: addCategory.value,
    coordinator_id: addCoordinatorId.value,
  })
  if (res.data.success) {
    addCoordinatorId.value = ''
    fetchAll()
  } else {
    err.value = res.data.error || 'Could not add assignment'
  }
}

async function removeAssignment(id) {
  const res = await axios.post(DOMAIN.concat(`/api/assignments/delete/${id}`))
  if (res.data.success) fetchAll()
  else err.value = res.data.error || 'Could not remove assignment'
}

async function uploadSpreadsheet(e) {
  err.value = null
  importSummary.value = null
  const file = e.target.files[0]
  if (!file) return
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await axios.post(DOMAIN.concat('/api/projects/import'), fd)
    if (res.data.success) {
      importSummary.value = res.data
      fetchAll()
    } else {
      err.value = res.data.error || 'Import failed'
    }
  } catch (ex) {
    err.value = ex?.response?.data?.error || 'Import failed'
  } finally {
    importing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

fetchAll()
</script>

<template>
  <div class="navigation">
    <RouterLink to="/">Home</RouterLink>
  </div>
  <h1>Project Assignments</h1>
  <p>
    A coordinator can edit any opportunity for a <b>project + category</b> they're assigned to.
    Admins edit everything; <b>AT</b> and <b>EV</b> are open to any coordinator.
  </p>

  <div class="import">
    <label class="vf-btn vf-btn-secondary">
      {{ importing ? 'Importing…' : 'Upload Projects spreadsheet (.xlsx)' }}
      <input ref="fileInput" type="file" accept=".xlsx" @change="uploadSpreadsheet" :disabled="importing" hidden />
    </label>
    <div v-if="importSummary" class="summary">
      Imported {{ importSummary.projects_upserted }} projects, created
      {{ importSummary.assignments_created }} new assignments.
      <span v-if="importSummary.unmatched_emails.length">· {{ importSummary.unmatched_emails.length }} unmatched email(s)
        <details><summary>show</summary>{{ importSummary.unmatched_emails.join(', ') }}</details>
      </span>
      <span v-if="importSummary.skipped_categories && importSummary.skipped_categories.length">
        · skipped categories: {{ importSummary.skipped_categories.join(', ') }}
      </span>
      <span v-if="importSummary.not_in_upload && importSummary.not_in_upload.length">
        · {{ importSummary.not_in_upload.length }} project(s) not in this upload (flagged below)
      </span>
    </div>
  </div>

  <form class="add-form" @submit.prevent="addAssignment">
    <select v-model="addProjectId">
      <option value="" disabled>Project…</option>
      <option v-for="p in projects" :key="p.project_id" :value="p.project_id">{{ p.project_id }} — {{ p.name }}</option>
    </select>
    <select v-model="addCategory" :disabled="!addProjectId">
      <option value="" disabled>Category…</option>
      <option v-for="c in addCategories" :key="c" :value="c">{{ c }}</option>
    </select>
    <select v-model="addCoordinatorId">
      <option value="" disabled>Coordinator…</option>
      <option v-for="c in coordinators" :key="c.id" :value="c.id">{{ c.email }}</option>
    </select>
    <button class="vf-btn vf-btn-primary" type="submit"
      :disabled="!addProjectId || !addCategory || !addCoordinatorId">Add</button>
  </form>
  <div class="error" v-if="err">{{ err }}</div>

  <table class="combos">
    <thead><tr><th>Project — Category</th><th>Coordinators</th><th>Status</th></tr></thead>
    <tbody>
      <tr v-for="combo in combos" :key="combo.project_id + '::' + combo.category" :class="{ 'stale-row': combo.stale }">
        <td>{{ combo.project_id }} {{ combo.name }} — <b>{{ combo.category }}</b></td>
        <td>
          <span v-for="a in coordsFor(combo)" :key="a.id" class="chip">
            {{ a.email }} <button class="chip-x" @click="removeAssignment(a.id)">×</button>
          </span>
          <span v-if="!coordsFor(combo).length" class="muted">—</span>
        </td>
        <td><span v-if="combo.stale" class="badge-stale">⚠ not in latest upload</span></td>
      </tr>
      <tr v-if="!combos.length"><td colspan="3"><i>No projects yet — upload the spreadsheet.</i></td></tr>
    </tbody>
  </table>
</template>

<style scoped>
  .navigation { text-align: right; }
  .import { margin: 16px 0; }
  .import label { cursor: pointer; }
  .summary { margin-top: 10px; font-size: .9em; }
  .summary details { display: inline; }
  .add-form { display: flex; gap: 10px; align-items: center; margin: 16px 0; flex-wrap: wrap; }
  .add-form select { height: 38px; padding: 0 8px; }
  .error { color: #b91c1c; margin: 8px 0; }
  .combos { border-collapse: collapse; width: 100%; max-width: 900px; }
  .combos th, .combos td { border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; vertical-align: top; }
  .stale-row { background: #fef2f2; }
  .badge-stale { color: #b91c1c; font-weight: 600; font-size: .85em; }
  .chip { display: inline-block; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 1px 8px; margin: 2px; font-size: .85em; }
  .chip-x { border: none; background: none; cursor: pointer; color: #b91c1c; font-weight: 700; }
  .muted { color: #9ca3af; }
</style>
