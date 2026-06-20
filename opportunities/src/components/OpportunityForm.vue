<script setup>
import axios from 'axios'
import moment from 'moment'
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'

import { AT_CATEGORIES, CATEGORY_CODES, CITIES, DOMAIN } from '../utils.js'

const props = defineProps({
  id: String
})

const router = useRouter()
const endpoint = ref(`${DOMAIN}/api/create`)
const user = ref({})
const form$ = ref(null)
const err = ref(null)
const success = ref(false)
const copy = ref(false)
const notDeleted = ref(true)

const currentType = ref('once')
const currentDays = ref([])

const typeOptions = { once: 'One Day', weekly: 'Weekly', monthly: 'Monthly', anytime: 'Anytime' }
const dayOptions = { '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat' }

const selectedWeekdayName = computed(() => {
  const dateVal = form$.value?.el$('ui_date')?.value;
  return dateVal ? moment(dateVal).format('dddd') : '';
});

function setType(val) {
  currentType.value = val
  if (form$.value?.el$('type')) form$.value.el$('type').update(val)
  // recurring_weekly/anytime are derived from the type. Their :value props only
  // seed the elements, so once form.load() has set them on an edit they no longer
  // track the type — push the derived values explicitly, same as `type` above.
  if (form$.value?.el$('recurring_weekly')) form$.value.el$('recurring_weekly').update(val === 'weekly')
  if (form$.value?.el$('anytime')) form$.value.el$('anytime').update(val === 'anytime')
  // Clear the monthly value when the type isn't monthly so a leftover number
  // can't make a one-day/weekly event expand as monthly in find_recurring.
  if (val !== 'monthly' && form$.value?.el$('recurring_monthly')) form$.value.el$('recurring_monthly').update(null)
}

function toggleDay(val) {
  let days = [...currentDays.value]
  if (days.includes(val)) {
    days = days.filter(d => d !== val)
  } else {
    days.push(val)
  }
  currentDays.value = days
  if (form$.value?.el$('recurring_days')) form$.value.el$('recurring_days').update(days)
}

function syncDatetime() {
  if (!form$.value) return
  const dateVal = form$.value.el$('ui_date').value;
  const startT = form$.value.el$('ui_start_time').value;
  const endT = form$.value.el$('ui_end_time').value;

  if (dateVal && startT) {
    const startStr = `${dateVal} ${startT}`;
    form$.value.el$('event_start').value = moment(startStr, 'YYYY-MM-DD HH:mm').format('YYYY-MM-DD HH:mm');
  }
  if (dateVal && endT) {
    const endStr = `${dateVal} ${endT}`;
    form$.value.el$('event_end').value = moment(endStr, 'YYYY-MM-DD HH:mm').format('YYYY-MM-DD HH:mm');
  }
}

watch([() => form$.value?.el$('ui_date')?.value, () => currentType.value], ([newDate, type]) => {
  if (!newDate || type !== 'weekly' || !form$.value) return;
  // Seed the anchor date's weekday only when nothing is chosen yet, so an
  // existing selection (loaded or user-picked) is never overridden.
  const dayIndex = moment(newDate).day().toString();
  if (currentDays.value.length === 0) toggleDay(dayIndex)
});

function duplicate() {
  endpoint.value = `${DOMAIN}/api/create`;
  copy.value = true;
}

async function deleteOpp() {
  notDeleted.value = false;
  const res = await axios.post(DOMAIN.concat(`/api/delete/${props.id}`));
  if (res.data.success) {
    success.value = true;
    setTimeout(() => router.push('/'), 2000);
  }
}

// Named function (not an inline template arrow) so `router` is in lexical scope.
function handleResponse(res) {
  if (res.data?.success) {
    success.value = true;
    setTimeout(() => router.push('/'), 2000);
  } else {
    err.value = 'Error';
  }
}

async function fetchOpportunity(id) {
  const res = await axios.get(DOMAIN.concat(`/api/opportunities/${id}`));
  const data = await res.data;

  if (data.anytime) data.type = 'anytime';
  else if (data.recurring_weekly) data.type = 'weekly';
  else if (data.recurring_monthly) data.type = 'monthly';
  else data.type = 'once';

  currentType.value = data.type;
  currentDays.value = data.recurring_days ? data.recurring_days.split(',') : [];

  // Show the day selector when the event repeats on more than one weekday.
  if (currentDays.value.length > 1) data.multiple_days = true;

  if (data.event_start && data.event_start !== "null" && moment(data.event_start).isValid()) {
    data.ui_date = moment(data.event_start).format('YYYY-MM-DD');
    data.ui_start_time = moment(data.event_start).format('HH:mm');
  }

  if (data.event_end && data.event_end !== "null" && moment(data.event_end).isValid()) {
    data.ui_end_time = moment(data.event_end).format('HH:mm');
  }

  if (!data.expiration_date || data.expiration_date === "null" || !moment(data.expiration_date).isValid()) {
    delete data.expiration_date;
  } else {
    data.expiration_date = moment(data.expiration_date).format('YYYY-MM-DD');
  }

  await nextTick();
  form$.value.load(data, true);
}

onMounted(async () => {
  const res = await axios.get(DOMAIN.concat(`/auth/user`));
  user.value = res.data;
  if (props.id) {
    fetchOpportunity(props.id);
    endpoint.value = `${DOMAIN}/api/update/${props.id}`;
  }
})
</script>

<template>
  <div class="form-outer-wrapper" :class="{ 'is-disabled': success }">
    <Vueform
      :endpoint="endpoint"
      @response="handleResponse"
      ref="form$"
      class="opportunity-form"
    >
      <template #empty>
        <FormSteps>
          <FormStep name="desc" label="Description" :elements="['title', 'body', 'category', 'project_id', 'at_category']" :labels="{ next: 'Continue to Where' }" />
          <FormStep name="where" label="Where" :elements="['anywhere', 'location', 'city']" :labels="{ next: 'Continue to When', previous: 'Back' }" />
          <FormStep name="when" label="When" :elements="['type', 'type_anchor', 'ui_date', 'p_weekday_display', 'multiple_days', 'days_anchor', 'ui_start_time', 'ui_end_time', 'recurring_monthly', 'expiration_date']" :labels="{ next: 'Continue to RSVP', previous: 'Back' }" />
          <FormStep name="rsvp" label="RSVP" :elements="['link', 'just_show_up']" :labels="{ finish: 'Submit', previous: 'Back' }" />
        </FormSteps>

        <div v-if="props.id" class="admin-actions-row">
          <button class="vf-btn vf-btn-primary" v-if="copy" disabled>Copied</button>
          <div v-else-if="notDeleted" class="admin-btn-flex">
            <button class="vf-btn vf-btn-primary" @click.prevent="duplicate">Copy</button>
            <button class="vf-btn vf-btn-danger" @click.prevent="deleteOpp">Delete</button>
          </div>
        </div>

        <FormElements>
          <HiddenElement name="owner" :value="user.admin && form$?.model?.owner ? form$.model.owner : user.id"/>
          <HiddenElement name="event_start" /><HiddenElement name="event_end" />
          <HiddenElement name="anytime" :value="currentType === 'anytime'"/>
          <HiddenElement name="recurring_weekly" :value="currentType === 'weekly'"/>
          <HiddenElement name="type" /><HiddenElement name="recurring_days" />

          <TextElement name="title" label="Title" rules="required" />
          <EditorElement name="body" label="Description" rules="required" />
          <SelectElement name="category" label="Category" :items="CATEGORY_CODES" rules="required" />
          <TextElement name="project_id" label="Project ID" rules="numeric" :conditions="[['category', 'not_in', ['AT', 'EV']]]" />
          <SelectElement name="at_category" label="Activity Type" :items="AT_CATEGORIES" :conditions="[['category', '==', 'AT']]" />

          <ToggleElement name="anywhere" label="This can be done anywhere" class="aligned-toggle" />
          <TextElement name="location" label="Location" :conditions="[['anywhere', '==', false]]" />
          <SelectElement name="city" label="City" :items="CITIES" :conditions="[['anywhere', '==', false]]" />

          <StaticElement name="type_anchor" content="<p class='custom-label'>Frequency</p><div id='type-target'></div>" />
          <DateElement name="ui_date" label="Event Date" value-format="YYYY-MM-DD" :time="false" :conditions="[['type', '!=', 'anytime']]" @change="syncDatetime" />

          <StaticElement
            name="p_weekday_display"
            :content="'<span style=\'font-size: 13px; color: #6b7280; font-weight: 400;\'>This date is a ' + selectedWeekdayName + '</span>'"
            tag="p"
            :conditions="[['type', '==', 'weekly']]"
          />

          <ToggleElement name="multiple_days" label="Repeat on multiple days each week?" :conditions="[['type', '==', 'weekly']]" class="aligned-toggle" />
          <StaticElement name="days_anchor" content="<div id='days-target'></div>" :conditions="[['type', '==', 'weekly'], ['multiple_days', '==', true]]" />

          <DateElement name="ui_start_time" label="Start Time" :date="false" :time="true" value-format="HH:mm" display-format="hh:mm a" :conditions="[['type', '!=', 'anytime']]" @change="syncDatetime" />
          <DateElement name="ui_end_time" label="End Time" :date="false" :time="true" value-format="HH:mm" display-format="hh:mm a" :conditions="[['type', '!=', 'anytime']]" @change="syncDatetime" />
          <TextElement name="recurring_monthly" label="Week of the month (1-5)" rules="required|numeric|min:1|max:5" :conditions="[['type', '==', 'monthly']]" />
          <DateElement name="expiration_date" label="Expiration Date" :time="false" value-format="YYYY-MM-DD" :conditions="[['type', '!=', 'once']]" />

          <TextElement name="link" label="Sign Up Link" />
          <ToggleElement name="just_show_up" label="Can volunteers just show up?" class="aligned-toggle" />
        </FormElements>

        <FormStepsControls />

        <div class="help">
          <a href="https://docs.google.com/document/d/1zqQsXDq8cU7HPE-stWppD7BPM8NVLXM18IK7-XABtmE/edit?usp=sharing" target="_blank">Help</a>
          <span class="footer-separator">|</span>
          <RouterLink to="/">Exit</RouterLink>
        </div>
      </template>
    </Vueform>

    <Teleport to="#type-target" v-if="form$">
      <div class="custom-btn-row">
        <button v-for="(label, key) in typeOptions" :key="key" type="button"
          class="manual-btn" :class="{ 'selected': currentType === key }" @click="setType(key)">
          {{ label }}
        </button>
      </div>
    </Teleport>
    <Teleport to="#days-target" v-if="form$">
      <div class="custom-btn-row">
        <button v-for="(label, key) in dayOptions" :key="key" type="button"
          class="manual-btn" :class="{ 'selected': currentDays.includes(key) }" @click="toggleDay(key)">
          {{ label }}
        </button>
      </div>
    </Teleport>
  </div>
</template>

<style>
  .opportunity-form { width: 600px; max-width: 100%; margin: auto; padding-top: 10px; }
  .admin-actions-row { display: flex; justify-content: flex-end; margin-bottom: 20px; }
  .admin-btn-flex { display: flex; gap: 12px; }

  .help { text-align: right; padding: 10px 0; }
  .help a, .help span, .help .RouterLink { color: #00bd7e !important; }
  .footer-separator { margin: 0 8px; color: #d1d5db; }

  .custom-btn-row { display: flex; width: 100%; gap: 5px; margin: 10px 0; }

  .manual-btn {
    flex: 1; height: 42px; border: 1px solid var(--vf-border-color-input, #d1d5db);
    border-radius: var(--vf-radius-input, 4px); background: white;
    color: var(--vf-color-input, #374151); font-weight: 600; cursor: pointer; transition: all 0.2s;
  }
  .manual-btn.selected {
    background-color: var(--vf-primary, #07bf9b) !important;
    border-color: var(--vf-primary, #07bf9b) !important;
    color: var(--vf-color-on-primary, white) !important;
  }

  .aligned-toggle [class*="-wrapper"] {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding-right: 0 !important;
  }
  .aligned-toggle [class*="-container"] {
    margin-left: auto !important;
    margin-right: 0 !important;
    flex-shrink: 0 !important;
  }
  .aligned-toggle [class*="-inner-wrapper-after"],
  .aligned-toggle [class*="-inner-wrapper-before"] {
    display: none !important;
    width: 0 !important;
  }

  .custom-label { margin-bottom: 5px; font-weight: 600; color: var(--vf-color-label, #374151); }

  .is-disabled { pointer-events: none; opacity: 0.6; }
</style>
