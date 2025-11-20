<script setup>
import axios from 'axios'
import { ref } from 'vue'

import User from './User.vue'
import { DOMAIN } from '../utils.js'

const users = ref([])

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
  <div v-for="user in users">
    <User :user="user"/>
  </div>
</template>

<style media="screen">
  .navigation {
    text-align: right;
  }
</style>
