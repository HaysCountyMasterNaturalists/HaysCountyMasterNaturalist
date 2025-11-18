<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { DOMAIN } from '../utils.js'


const props = defineProps({
  key: String
})

const router = useRouter()
const endpoint = ref(`${DOMAIN}/auth/reset-password`)
const err = ref()

function handleResponse(response) {
  if (response.data.success) {
    router.push('/')
  } else {
    err.value = 'Oops! Something went wrong. Please try again.'
    setTimeout(() => {
      err.value = null
    }, 5000);
  }
}
</script>

<template>
  <div class="auth-form">
    <h1>Reset Password</h1>
    <div class="error" v-if="err">{{ err }}</div>
    <Vueform
      size="lg"
      :endpoint="endpoint"
      @response="handleResponse"
    >
        <StaticElement
          content="Password"
          tag="p"
        />
        <TextElement
          name="password"
          input-type="password"
          placeholder="Password"
          :rules="[
            'required',
            'same:password_confirmation',
          ]"

        />
        <StaticElement
          content="Confirm Password"
          tag="p"
        />
        <TextElement
          name="password_confirmation"
          input-type="password"
          :rules="[
            'required',
          ]"
          placeholder="Confirm Password"
        />
        <ButtonElement
          name="submit"
          :submits="true"
          button-label="Submit"
          :full="true"
          size="lg"
        />
    </Vueform>
  </div>
</template>

<style media="screen">
  .auth-form {
    width: 100%;
    max-width: 600px;
    margin: auto;
  }
</style>
