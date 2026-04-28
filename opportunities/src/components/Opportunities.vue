<script setup>
import axios from 'axios'
import moment from 'moment'
import { computed, ref, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ModalsContainer, VueFinalModal } from 'vue-final-modal'

import Day from './Day.vue'
import OpportunityModal from './OpportunityModal.vue'
import { getCategory, DOMAIN } from '../utils.js'

// UI-controlled toggle for week start behavior
// true  -> weeks start on Sunday (today if Sunday, otherwise previous Sunday)
// false -> original behavior (today-based)
const startWeekOnSunday = ref(false)

const ANY_TIME = 'Any Time'

// Calendar range (avoid magic numbers)
const DAYS_BACK = 45
const DAYS_FORWARD = 181
const opportunities = ref([])
const categories = ref([])
const cities = ref([])
const searchTitleAndBody = ref(null)
const selectedCategories = ref(new Set())
const selectedCities = ref(new Set())
const showExpired = ref(false)
const filteredOpportunities = ref({})
const user = ref({})
const days = ref([])
const openOpp = ref({})
const openedOpp = ref(false)

// How many days back the calendar extends
const LOOKBACK_DAYS = 45

// Index where the visible 7-column grid starts
const visibleStartIndex = ref(DAYS_BACK + 1)

const router = useRouter()
const route = useRoute()

// Sticky filters: localStorage + URL query sync
const STORAGE_KEY = 'opportunities_filters_v1'
const isHydratingFilters = ref(true)

// App update banner (manual version/date + description)
// Bump APP_UPDATE_DATE (YYYY-MM-DD) and APP_UPDATE_DESC whenever you ship a notable UI/app change.
const APP_UPDATE_DATE = '2026-02-07'
const APP_UPDATE_DESC = 'Filters now persist across refresh and can be shared via the URL query string.'
const UPDATE_COOKIE_KEY = 'opportunities_last_seen_update'
const showUpdateBanner = ref(false)

function getCookie(name) {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\/\+^])/g, '\$1') + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

function setCookie(name, value, days = 365) {
  if (typeof document === 'undefined') return
  const expires = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toUTCString()
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`
}

function shouldShowUpdateBanner() {
  const seen = getCookie(UPDATE_COOKIE_KEY)
  if (!seen) return true
  // Compare as dates; cookie stores the same YYYY-MM-DD format
  return moment(seen, 'YYYY-MM-DD', true).isValid()
    ? moment(seen, 'YYYY-MM-DD').isBefore(moment(APP_UPDATE_DATE, 'YYYY-MM-DD'), 'day')
    : true
}

function dismissUpdateBanner() {
  setCookie(UPDATE_COOKIE_KEY, APP_UPDATE_DATE)
  showUpdateBanner.value = false
}

function parseListParam(v) {
  if (!v) return []
  if (Array.isArray(v)) return v.flatMap(x => String(x).split(',')).filter(Boolean)
  return String(v).split(',').filter(Boolean)
}

function safeJSONParse(s) {
  try {
    return JSON.parse(s)
  } catch (e) {
    return null
  }
}

function hydrateFiltersFromQuery(q) {
  // q: title/body search
  if (typeof q.q === 'string') {
    searchTitleAndBody.value = q.q || null
  }

  // expired: 1/0
  if (q.expired !== undefined) {
    showExpired.value = String(q.expired) === '1' || String(q.expired).toLowerCase() === 'true'
  }

  // sunday: 1/0 (default is false)
  if (q.sunday !== undefined) {
    startWeekOnSunday.value = String(q.sunday) === '1' || String(q.sunday).toLowerCase() === 'true'
  }

  // categories + cities
  const catList = parseListParam(q.categories)
  const cityList = parseListParam(q.cities)

  if (catList.length) selectedCategories.value = new Set(catList)
  if (cityList.length) selectedCities.value = new Set(cityList)
}

function hydrateFiltersFromStorage() {
  if (typeof window === 'undefined') return
  const raw = window.localStorage.getItem(STORAGE_KEY)
  const stored = raw ? safeJSONParse(raw) : null
  if (!stored || typeof stored !== 'object') return

  if (stored.q !== undefined) searchTitleAndBody.value = stored.q || null
  if (stored.showExpired !== undefined) showExpired.value = !!stored.showExpired
  if (stored.startWeekOnSunday !== undefined) startWeekOnSunday.value = !!stored.startWeekOnSunday

  if (Array.isArray(stored.categories)) selectedCategories.value = new Set(stored.categories)
  if (Array.isArray(stored.cities)) selectedCities.value = new Set(stored.cities)
}

function buildQueryFromFilters() {
  const query = {}

  if (searchTitleAndBody.value) query.q = searchTitleAndBody.value
  if (showExpired.value) query.expired = '1'

  // Always include the sunday parameter to avoid confusion
  query.sunday = startWeekOnSunday.value ? '1' : '0'

  if (selectedCategories.value.size) query.categories = Array.from(selectedCategories.value).join(',')
  if (selectedCities.value.size) query.cities = Array.from(selectedCities.value).join(',')

  return query
}

function persistFilters() {
  if (typeof window !== 'undefined') {
    const payload = {
      q: searchTitleAndBody.value,
      showExpired: showExpired.value,
      startWeekOnSunday: startWeekOnSunday.value,
      categories: Array.from(selectedCategories.value),
      cities: Array.from(selectedCities.value)
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  }
}

function syncUrlQuery() {
  const nextQuery = buildQueryFromFilters()

  // Avoid needless router updates (and keep back button sane)
  const current = route.query || {}
  const currStr = JSON.stringify(current)
  const nextStr = JSON.stringify(nextQuery)
  if (currStr === nextStr) return

  router.replace({ query: nextQuery })
}

// Days actually rendered in the grid.
// IMPORTANT: Always include ANY_TIME (index 0), even when slicing the date range.
const displayDays = computed(() => {
  const dateSlice = days.value.slice(visibleStartIndex.value)
  return [ANY_TIME, ...dateSlice]
})

function addRemoveCategory(e, category) {
  selectedCategories.value.has(category)
    ? selectedCategories.value.delete(category)
    : selectedCategories.value.add(category)

  selectedCategories.value = new Set(selectedCategories.value)
}

function addRemoveCity(e, city) {
  selectedCities.value.has(city)
    ? selectedCities.value.delete(city)
    : selectedCities.value.add(city)

  selectedCities.value = new Set(selectedCities.value)
}

function orderByDate(opps) {
  opps.sort((a, b) => {
    const aTime = a.event_start ? moment(a.event_start) : moment()
    const bTime = b.event_start ? moment(b.event_start) : moment()
    return aTime > bTime ? 1 : -1
  })
}

function removeExpired(opps) {
  return opps.filter((opp) => {
    let expirationDate
    if (opp.expiration_date && opp.event_start) {
      expirationDate = moment(opp.expiration_date) >= moment(opp.event_start)
        ? opp.event_start
        : opp.expiration_date
    } else {
      expirationDate = opp.expiration_date || opp.event_start
    }

    return !expirationDate || moment() <= moment(expirationDate)
  })
}

function isPastDay(dayLabel) {
  if (dayLabel === ANY_TIME) return false
  const day = moment(dayLabel, 'LLLL')
  return day.isBefore(moment(), 'day')
}

function getReadableDate(day) {
  return day.format('LLLL').replace(' '.concat(day.format('LT')), '').slice(0, -6)
}

function groupByDay(opps) {
  const opportunitiesByDay = {}
  opps.forEach((opp) => {
    const day = opp.event_start
      ? getReadableDate(moment(opp.event_start))
      : ANY_TIME

    opportunitiesByDay[day] ||= []
    opportunitiesByDay[day].push(opp)
  })
  return opportunitiesByDay
}

function getAllDays() {
  days.value = [ANY_TIME]

  // Base range starts DAYS_BACK days ago.
  // If weeks start on Sunday, shift startDay back to the previous Sunday so the first column aligns.
  const baseStart = moment().subtract(DAYS_BACK, 'days')
  const padToSunday = startWeekOnSunday.value ? baseStart.day() : 0 // 0=Sun..6=Sat
  const startDay = moment(baseStart).subtract(padToSunday, 'days')

  const totalDays = DAYS_BACK + DAYS_FORWARD + padToSunday

  // When NOT showing expired, we start the grid at either:
  // - Sunday of the current week (if startWeekOnSunday)
  // - Today (original behavior)
  if (startWeekOnSunday.value) {
    const weekStartSunday = moment().subtract(moment().day(), 'days')
    visibleStartIndex.value = 1 + weekStartSunday.diff(startDay, 'days')
  } else {
    // days[0] is ANY_TIME, so today is at index (1 + DAYS_BACK)
    visibleStartIndex.value = 1 + DAYS_BACK
  }

  let day = moment(startDay)
  for (let i = 0; i < totalDays; i++) {
    days.value.push(getReadableDate(day))
    day = day.add(1, 'days')
  }
}

function filterOpportunities() {
  let newOpps = [...opportunities.value]

  // When showExpired is OFF, remove expired items
  if (!showExpired.value) {
    newOpps = removeExpired(newOpps)
  }

  if (searchTitleAndBody.value) {
    const q = searchTitleAndBody.value.toLowerCase()
    newOpps = newOpps.filter(o =>
      o.title.toLowerCase().includes(q) || o.body.toLowerCase().includes(q)
    )
  }

  if (selectedCities.value.size) {
    newOpps = newOpps.filter(o =>
      selectedCities.value.has(o.anywhere ? 'Anywhere' : o.city)
    )
  }

  if (selectedCategories.value.size) {
    newOpps = newOpps.filter(o =>
      selectedCategories.value.has(getCategory(o.category))
    )
  }

  filteredOpportunities.value = groupByDay(newOpps)
}

function openModal(opp) {
  openOpp.value = opp
  openedOpp.value = true
}

function closeModal() {
  openOpp.value = {}
  openedOpp.value = false
}

async function logout() {
  const res = await axios.post(DOMAIN.concat('/auth/logout'))

  if (res.data.success) router.go(0)
}

async function fetchOpportunities() {
  const res = await axios.get(DOMAIN.concat('/api/opportunities'))
  opportunities.value = res.data

  cities.value = Array.from(new Set(opportunities.value.map(o => o.city || 'Anywhere'))).sort()
  categories.value = Array.from(new Set(opportunities.value.map(o => getCategory(o.category)))).sort()

  orderByDate(opportunities.value)
  filterOpportunities()
  getAllDays()
}

async function fetchUser() {
  const res = await axios.get(DOMAIN.concat('/auth/user'))

  const u = res.data
  user.value = {
    ...u,
    admin: !!u.admin,
    project_coordinator: !!u.project_coordinator
  }
}

watch([searchTitleAndBody, selectedCities, selectedCategories, showExpired], filterOpportunities)
watch(startWeekOnSunday, getAllDays)

// Persist + sync URL whenever a filter changes
watch(
  [searchTitleAndBody, selectedCities, selectedCategories, showExpired, startWeekOnSunday],
  () => {
    if (isHydratingFilters.value) return
    persistFilters()
    syncUrlQuery()
  },
  { flush: 'post' }
)

// Hydrate filters once on mount: querystring wins over localStorage
onMounted(() => {
  // Update banner: show only if user hasn't dismissed this (or has dismissed an older one)
  showUpdateBanner.value = shouldShowUpdateBanner()

  hydrateFiltersFromStorage()
  hydrateFiltersFromQuery(route.query || {})

  // If we hydrated from storage (or query), make URL reflect current state
  isHydratingFilters.value = false
  persistFilters()
  syncUrlQuery()
})

fetchOpportunities()
fetchUser()
</script>

<template>
  <div v-if="showUpdateBanner" class="update-banner">
    <div class="update-banner__content">
      <strong>Update ({{ APP_UPDATE_DATE }}):</strong>
      <span class="update-banner__desc">{{ APP_UPDATE_DESC }}</span>
    </div>
    <button class="update-banner__dismiss" type="button" @click="dismissUpdateBanner">
      Dismiss
    </button>
  </div>

  <div class="user">
    <div v-if="user.id">
      <RouterLink v-if="user.admin || user.project_coordinator" to="/new">Create Opportunity</RouterLink>
      <a v-else href="https://docs.google.com/forms/d/e/1FAIpQLSf0j6GQVsDAo0UZswqfXhGRk7l5HcoEhqOvnsmudf5KhiDLrA/viewform?usp=sf_link">Request Editing Access</a>
      <span> | </span>
      <RouterLink v-if="user.admin" to="/users">Manage Users</RouterLink>
      <span v-if="user.admin"> | </span>
      <a href="#" @click.stop.prevent="logout">Logout</a>
    </div>
    <div v-else>
      Project Coordinators:
      <RouterLink to="/signup">Sign Up</RouterLink> |
      <RouterLink to="/login">Log in</RouterLink>
    </div>
  </div>

  <div class="everything">
    <div class="filters">
      <div class="filter">
        <label><h3>Search</h3></label>
        <input v-model="searchTitleAndBody" />
        <br /><br />
        <label>
          <input type="checkbox" v-model="showExpired" />
          Show expired opportunities
        </label>
        <br />
        <label>
          <input type="checkbox" v-model="startWeekOnSunday" />
          Start week on Sunday
        </label>
      </div>

      <div class="filter">
        <h3>Categories</h3>
        <div v-for="category in categories" :key="category">
          <label>
            <input
              type="checkbox"
              @change="addRemoveCategory($event, category)"
              :value="category"
              :checked="selectedCategories.has(category)"
            />
            {{ category }}
          </label>
        </div>
      </div>

      <div class="filter">
        <h3>Cities</h3>
        <div v-for="city in cities" :key="city">
          <label>
            <input
              type="checkbox"
              @change="addRemoveCity($event, city)"
              :value="city"
              :checked="selectedCities.has(city)"
            />
            {{ city }}
          </label>
        </div>
      </div>
    </div>

    <div class="weeks">
      <div
        class="day"
        v-for="day in (showExpired ? days : displayDays)"
        :key="day"
        :class="{ 'any-time-day': day === ANY_TIME && startWeekOnSunday }"
      >
        <div class="day-header">{{ day }}</div>

        <div v-if="!showExpired && isPastDay(day)" class="opp-placeholder opp opportunity past">
          <span class="icon">⏱</span>
          <span>Expired</span>
        </div>

        <template v-if="(filteredOpportunities[day] || []).length">
          <div :class="{ 'any-time-opps': day === ANY_TIME && startWeekOnSunday }">
            <Day
              :admin="user.admin"
              :userId="user.id"
              :opps="filteredOpportunities[day]"
              @modalOpp="openModal"
            />
          </div>
        </template>

        <div v-else-if="!((!showExpired) && isPastDay(day))" class="opp-placeholder opp opportunity no-matches">
          <span class="icon">⛔</span>
          <span>None</span>
        </div>
      </div>
    </div>
  </div>

  <VueFinalModal v-model="openedOpp">
    <OpportunityModal :opp="openOpp" @closeModal="closeModal" />
  </VueFinalModal>
  <ModalsContainer />
</template>

<style scoped>
.update-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid #d4b106;
  border-radius: 8px;
  background: #fffbe6;
  color: #594d00;
}

.update-banner__content {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.update-banner__desc {
  font-weight: 500;
}

.update-banner__dismiss {
  border: 1px solid #ccc;
  background: white;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
}

.user { text-align: right; }
.filters { line-height: 1.5; margin-right: 10px; }
.filter { margin: 20px; }
.day-header { padding: 5px; color: #2c3e50; }

@media (prefers-color-scheme: dark) {
  .day-header { color: #ffffff; }
}

.week-header {
  display: flex;
  width: 100%;
}
.weekday {
  width: 14%;
  padding: 5px;
  font-weight: 600;
  text-align: center;
}

.opp-placeholder {
  background: #eee;
  border: 1px solid #ccc;
  border-radius: 6px;
  padding: 10px;
  margin: 10px 6px;
  box-sizing: border-box;
  display: flex;
  gap: 8px;
  align-items: center;
  color: #555;
}

.opp-placeholder .icon {
  font-size: 1.1em;
}

.opp-placeholder span:last-child {
  font-weight: 700;
}

@media (min-width: 1024px) {
  .weeks {
    display: flex;
    flex-wrap: wrap;
  }
  .day {
    flex-grow: 1;
    width: 14%;
  }
  .any-time-day {
    flex-basis: 100%;
    width: 100%;
  }

  /* Any Time: lay out opportunity cards in a 7-column grid to match the weekday columns below */
  .any-time-opps {
    display: grid;
    /* Up to 7 items per row; fewer items expand to fill the full width ("justify" across the row) */
    grid-template-columns: repeat(auto-fit, minmax(14.2857%, 1fr));
    align-items: start;
  }

  /* Make the <Day> component's root element disappear as a grid item so its children become the grid items */
  .any-time-opps > :first-child {
    display: contents;
  }

  /* Reach into <Day> component content */
  .any-time-opps :deep(.opp),
  .any-time-opps :deep(.opportunity) {
    width: 100%;
    box-sizing: border-box;
  }

  .filters { display: flex; }
}
</style>
