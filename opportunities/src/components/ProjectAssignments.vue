<script setup>
import axios from 'axios'
import { ref, computed } from 'vue'
import { VueFinalModal } from 'vue-final-modal'

import { AT_CATEGORIES, DOMAIN } from '../utils.js'

const assignments = ref([])   // {id, project_id, category, coordinator_id, email}
const users = ref([])
const projects = ref([])      // {project_id, name, categories:[], stale}
const err = ref(null)

const importSummary = ref(null)
const importing = ref(false)
const fileInput = ref(null)

const search = ref('')

// Per-row edit dialog
const showEdit = ref(false)
const editingCombo = ref(null)
const addCoordinatorId = ref('')

const coordinators = computed(() =>
  users.value.filter(u => u.project_coordinator || u.admin)
)

// Coordinators not already assigned to the row being edited.
const availableCoordinators = computed(() => {
  if (!editingCombo.value) return []
  const assignedIds = new Set(coordsFor(editingCombo.value).map(a => a.coordinator_id))
  return coordinators.value.filter(c => !assignedIds.has(c.id))
})

// One row per entry, in the same order as the opportunity dropdown: AT
// activity types first, then EV, then each project's (project, category)
// combos. AT and EV are exempt — open to any coordinator, no assignment row.
const combos = computed(() => {
  const rows = AT_CATEGORIES.map(at => ({
    key: `AT::${at}`,
    label: `AT — ${at}`,
    exempt: true,
  }))
  rows.push({ key: 'EV::', label: 'EV — Event', exempt: true })
  projects.value.forEach(p =>
    (p.categories || []).forEach(cat =>
      rows.push({
        key: `${p.project_id}::${cat}`,
        label: `${p.project_id} ${p.name} — ${cat}`,
        project_id: p.project_id,
        category: cat,
        stale: p.stale,
        exempt: false,
      })
    )
  )
  return rows
})

// Rows matching the search box (case-insensitive substring of the label).
const filteredCombos = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return combos.value
  return combos.value.filter(c => c.label.toLowerCase().includes(q))
})

function openEdit(combo) {
  editingCombo.value = combo
  addCoordinatorId.value = ''
  err.value = null
  showEdit.value = true
}

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
  if (!editingCombo.value || !addCoordinatorId.value) return
  const res = await axios.post(DOMAIN.concat('/api/assignments'), {
    project_id: editingCombo.value.project_id,
    category: editingCombo.value.category,
    coordinator_id: addCoordinatorId.value,
  })
  if (res.data.success) {
    addCoordinatorId.value = ''
    fetchAll()
  } else {
    err.value = res.data.error || 'Could not add assignment'
  }
}

async function removeAssignment(assignment) {
  if (!confirm(`Remove ${assignment.email} as a coordinator for this project/category?`)) return
  const res = await axios.post(DOMAIN.concat(`/api/assignments/delete/${assignment.id}`))
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

  <div class="error" v-if="err">{{ err }}</div>

  <div class="search">
    <input v-model="search" type="search" placeholder="Filter by project name, number or category…" />
  </div>

  <table class="combos">
    <thead><tr>
      <th class="col-name">Project / Activity — Category</th>
      <th>Coordinators</th>
      <th>Status</th>
      <th></th>
    </tr></thead>
    <tbody>
      <tr v-for="combo in filteredCombos" :key="combo.key" :class="{ 'stale-row': combo.stale }">
        <td class="col-name">{{ combo.label }}</td>
        <td>
          <template v-if="combo.exempt">
            <span class="muted">any coordinator</span>
          </template>
          <template v-else>
            <span v-for="a in coordsFor(combo)" :key="a.id" class="chip">{{ a.email }}</span>
            <span v-if="!coordsFor(combo).length" class="muted">—</span>
          </template>
        </td>
        <td>
          <span v-if="combo.exempt" class="badge-ok">always available</span>
          <span v-else-if="combo.stale" class="badge-stale">⚠ not in latest upload</span>
          <span v-else class="badge-ok">✓ in latest upload</span>
        </td>
        <td class="col-edit">
          <button v-if="!combo.exempt" class="vf-btn vf-btn-secondary edit-btn" @click="openEdit(combo)">Edit</button>
        </td>
      </tr>
      <tr v-if="!filteredCombos.length"><td colspan="4"><i>No rows match “{{ search }}”.</i></td></tr>
    </tbody>
  </table>

  <VueFinalModal v-model="showEdit">
    <div class="modal-container" @click.self="showEdit = false">
      <div v-if="editingCombo" class="modal-box">
        <span class="close" @click="showEdit = false">&times;</span>
        <h2>Coordinators</h2>
        <p class="combo-label">{{ editingCombo.label }}</p>

        <ul class="coord-list">
          <li v-for="a in coordsFor(editingCombo)" :key="a.id">
            <span>{{ a.email }}</span>
            <button class="vf-btn vf-btn-secondary remove-btn" @click="removeAssignment(a)">Remove</button>
          </li>
          <li v-if="!coordsFor(editingCombo).length" class="muted">No coordinators assigned yet.</li>
        </ul>

        <form class="add-form" @submit.prevent="addAssignment">
          <select v-model="addCoordinatorId">
            <option value="" disabled>Add a coordinator…</option>
            <option v-for="c in availableCoordinators" :key="c.id" :value="c.id">{{ c.email }}</option>
          </select>
          <button class="vf-btn vf-btn-primary" type="submit" :disabled="!addCoordinatorId">Add</button>
        </form>
        <div class="error" v-if="err">{{ err }}</div>

        <div class="modal-actions">
          <button class="vf-btn vf-btn-secondary" @click="showEdit = false">Done</button>
        </div>
      </div>
    </div>
  </VueFinalModal>
</template>

<style scoped>
  .navigation { text-align: right; }
  .import { margin: 16px 0; }
  .import label { cursor: pointer; }
  .summary { margin-top: 10px; font-size: .9em; }
  .summary details { display: inline; }
  .error { color: #b91c1c; margin: 8px 0; }
  .search { margin: 12px 0; }
  .search input { width: 100%; max-width: 420px; height: 36px; padding: 0 10px; box-sizing: border-box; }
  .combos { border-collapse: collapse; width: 100%; max-width: 1000px; }
  .combos th, .combos td { border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; vertical-align: top; }
  .col-name { min-width: 420px; }
  .col-edit { text-align: center; white-space: nowrap; }
  .edit-btn { padding: 2px 12px; }
  .stale-row { background: #fef2f2; }
  .badge-stale { color: #b91c1c; font-weight: 600; font-size: .85em; }
  .badge-ok { color: #6b7280; font-size: .85em; }
  .chip { display: inline-block; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 1px 8px; margin: 2px; font-size: .85em; }
  .muted { color: #9ca3af; }

  /* Edit dialog — render our own overlay + box inside the modal slot (scoped
     styles can't reach vue-final-modal's teleported content wrapper). */
  .modal-container {
    position: fixed; inset: 0; z-index: 1000;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.5); padding: 20px;
  }
  .modal-box {
    position: relative; background: #fff; border-radius: 8px; padding: 20px 24px;
    width: 100%; max-width: 480px; max-height: 80vh; overflow-y: auto;
  }
  .close {
    position: absolute; top: 8px; right: 14px;
    font-size: 26px; font-weight: bold; color: #aaa; cursor: pointer; line-height: 1;
  }
  .close:hover { color: #000; }
  .combo-label { font-weight: 600; margin-top: 0; }
  .coord-list { list-style: none; padding: 0; margin: 0 0 16px; }
  .coord-list li { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 4px 0; border-bottom: 1px solid #f1f5f9; }
  .remove-btn { padding: 1px 10px; font-size: .85em; }
  .add-form { display: flex; gap: 10px; align-items: center; margin: 8px 0; flex-wrap: wrap; }
  .add-form select { height: 38px; padding: 0 8px; flex: 1; min-width: 200px; }
  .modal-actions { margin-top: 16px; text-align: right; }
</style>
