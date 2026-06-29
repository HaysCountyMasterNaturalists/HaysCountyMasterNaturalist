<script setup>
import axios from 'axios'
import { ref, computed } from 'vue'

import { DOMAIN } from '../utils.js'
import { userType } from '../permissions.js'

const props = defineProps({
  user: Object
})
const working = ref(false)
const passwordResetLink = ref('')

const typeLabel = computed(() => userType(props.user))


async function updateUser(user, privilege, event) {
  const turningOn = user[privilege] !== 1
  const label = privilege === 'admin' ? 'admin' : 'coordinator'
  const ok = confirm(
    `${turningOn ? 'Grant' : 'Remove'} ${label} ${turningOn ? 'to' : 'from'} ${user.email}?`
  )
  if (!ok) {
    // Revert the checkbox the browser already toggled.
    if (event && event.target) event.target.checked = user[privilege] === 1
    return
  }
  working.value = true
  user[privilege] = turningOn ? 1 : 0
  const res = await axios.post(DOMAIN.concat(`/api/users/${user.id}`), {
    admin: user.admin === 1,
    project_coordinator: user.project_coordinator === 1,
  }, {
    headers: {
      'Content-Type': 'application/json'
    }
  })
  let success = await res.data
  working.value = false
}

async function getPasswordResetLink() {
  const res = await axios.get(DOMAIN.concat(`/auth/users/reset-password/${props.user.id}`))
  let secretKey = await res.data.secret_key
  passwordResetLink.value = window.location.origin.concat(`/reset-password/${secretKey}/${props.user.id}`)
  navigator.clipboard.writeText(passwordResetLink.value)
}
</script>

<template>
  <tr>
    <td class="user-email">{{ props.user.email }}</td>
    <td>{{ typeLabel }}</td>
    <td>{{ props.user.last_login || '—' }}</td>
    <td>
      <ul v-if="props.user.assigned_projects && props.user.assigned_projects.length" class="projects">
        <li v-for="p in props.user.assigned_projects" :key="p.project_id + '::' + p.category">
          {{ p.project_id }} — {{ p.name || '(unnamed)' }} — <b>{{ p.category }}</b>
        </li>
      </ul>
      <span v-else class="muted">—</span>
    </td>
    <td class="manage">
      <label>Admin <input
        type="checkbox"
        :checked="props.user.admin"
        :disabled="working"
        @change="updateUser(props.user, 'admin', $event)" /></label>
      <label>Coordinator <input
        type="checkbox"
        :checked="props.user.project_coordinator"
        :disabled="working"
        @change="updateUser(props.user, 'project_coordinator', $event)"/></label>
      <div v-if="passwordResetLink" class="reset-link">{{ passwordResetLink }}</div>
      <button v-else @click.prevent="getPasswordResetLink">Get Password Reset Link</button>
    </td>
  </tr>
</template>

<style scoped>
  .projects {
    margin: 0;
    padding-left: 18px;
    font-size: .9em;
  }
  .projects li { margin: 1px 0; }
  .muted { color: #9ca3af; }
  .manage label { display: block; white-space: nowrap; }
  .reset-link { font-size: .8em; word-break: break-all; max-width: 320px; }
</style>
