<script setup>
import axios from 'axios'
import { ref } from 'vue'

import { DOMAIN } from '../utils.js'

const props = defineProps({
  user: Object
})
const working = ref(false)
const passwordResetLink = ref('')


async function updateUser(user, privilege) {
  working.value = true
  user[privilege] = user[privilege] === 1 ? 0 : 1
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
  <br/>
  <h2 class="user-email">{{ props.user.email }}</h2> 
  Admin <input
    type="checkbox"
    :checked="props.user.admin"
    :disabled="working"
    @change="updateUser(props.user, 'admin')" />
  <br/>
  Project Coordinator <input
    type="checkbox"
    :checked="props.user.project_coordinator" 
    :disabled="working"
    @change="updateUser(props.user, 'project_coordinator')"/>
  <div v-if="passwordResetLink">{{ passwordResetLink }}</div>
  <div v-else ><button @click.prevent="getPasswordResetLink">Get Password Reset Link</button></div>
</template>

<style media="screen">
</style>
