import './assets/main.css'

import { createApp } from 'vue'
import Vueform from '@vueform/vueform'
import vueformConfig from './../vueform.config'
import { createVfm } from 'vue-final-modal'
import { createWebHistory, createRouter } from 'vue-router'
import App from './App.vue'
import axios from 'axios'

import Opportunities from './components/Opportunities.vue'
import OpportunityForm from './components/OpportunityForm.vue'
import Auth from './components/Auth.vue'
import Users from './components/Users.vue'
import ResetPassword from './components/ResetPassword.vue'


axios.defaults.withCredentials = true
axios.defaults.headers.common['X-CSRFToken'] = window.CSRF_TOKEN
axios.interceptors.response.use((response) => {
  axios.defaults.headers.common['X-CSRFToken'] = response.headers['csrf-token']

  return response
})

const routes = [
  { path: '/', component: Opportunities },
  { path: '/signup', component: Auth, props: { endpoint: 'signup', title: 'Sign Up' } },
  { path: '/login', component: Auth, props: { endpoint: 'login', title: 'Log In' } },
  { path: '/reset-password/:token?/:id(\\d+)', component: ResetPassword, props: true },
  { path: '/new', component: OpportunityForm, props: {id: ''} },
  { path: '/:id', component: OpportunityForm, props: true },
  { path: '/users', component: Users },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)

app.use(Vueform, vueformConfig)
app.use(router)

const vfm = createVfm()
app.use(vfm) // vue final modal registration

app.mount('#app')
