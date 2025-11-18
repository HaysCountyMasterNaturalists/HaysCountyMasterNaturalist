<script setup>
import axios from 'axios'
import { ref, watch } from 'vue'
import { Validator } from '@vueform/vueform'
import { useRouter } from 'vue-router'

import { AT_CATEGORIES, CATEGORY_CODES, CITIES, DOMAIN, findDefaultEndTime } from '../utils.js'

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
const defaultEndTime = ref('')
const notDeleted = ref(true)


function handleResponse(response) {
  if (response.data.success) {
    success.value = true
    setTimeout(() => router.push('/'), 2000)
  } else {
    err.value = 'Oops! Something went wrong. Please try again.'
    setTimeout(() => {
      err.value = null
    }, 5000);
  }
}

function duplicate() {
  endpoint.value = `${DOMAIN}/api/create`
  copy.value = true
}

function setEndpoint(id) {
  endpoint.value = `${DOMAIN}/api/update/${id}`
}

function updateEndTime(newStartTime, oldValue, el$) {
  let eventEnd = el$.form$.el$('event_end')
  if (!newStartTime) {
    defaultEndTime.value = ''
    eventEnd.clear()
    eventEnd.update()
  } else {
    const newEndTime = findDefaultEndTime(newStartTime)
    if (defaultEndTime.value === '' || 
      defaultEndTime.value < newEndTime || 
      defaultEndTime.value.slice(0, 10) !== newEndTime.slice(0, 10)) {
        defaultEndTime.value = newEndTime
        eventEnd.clear()
        eventEnd.update()
    }
  }
}

async function deleteOpp() {
  notDeleted.value = false
  const res = await axios.post(DOMAIN.concat(`/api/delete/${props.id}`))
  const data = await res.data
  if (data.success) {
    success.value = true
    setTimeout(() => router.push('/'), 2000)
  }
}

async function fetchUser() {
  const res = await axios.get(DOMAIN.concat(`/auth/user`))
  user.value = await res.data
}

async function fetchOpportunity(id) {
  const res = await axios.get(DOMAIN.concat(`/api/opportunities/${id}`))
  const data = await res.data
  form$.value.load(data, true)
}


if (props.id.length) {
  fetchOpportunity(props.id)
  setEndpoint(props.id)
}

fetchUser()
 </script>

 <template>
  <Vueform
    :disabled="success"
    :endpoint="endpoint"
    @response="handleResponse"
    ref="form$"
    class="opportunity-form"
  >
     <template #empty>

       <FormSteps>
         <FormStep
           name="opp_description"
           label="Opportunity Description"
           :elements="[
            'p_title',
            'title',
            'p_description',
            'body',
            'p_category',
            'category',
            'p_project',
            'project_id',
            'at_category',
            'at_category_p'
           ]"
           :labels="{
             next: 'Continue to Where',
           }"
         />

         <FormStep
           name="opp_where"
           label="Where"
           :elements="[
            'p_anywhere',
            'anywhere',
            'p_location',
            'location',
            'p_city',
            'city'
           ]"
           :labels="{
             next: 'Continue to When',
             previous: 'Back'
           }"
         />

         <FormStep
           name="opp_when"
           label="When"
           :elements="[
            'p_anytime',
            'anytime',
            'p_start',
            'event_start',
            'p_end',
            'event_end',
            'p_expire',
            'expiration_date',
            'p_recurring_w',
            'recurring_weekly',
            'p_recurring_m',
            'recurring_monthly'
           ]"
           :labels="{
             finish: 'Coninue to RSVP',
             previous: 'Back'
           }"
         />

         <FormStep
           name="sign_up"
           label="RSVP"
           :elements="['p_link', 'link', 'p_show_up', 'just_show_up']"
           :labels="{
             finish: 'Submit',
             previous: 'Back'
           }"
         />
       </FormSteps>
       <div class="error" v-if="err">{{ err }}</div>
       <div class="success" v-if="success">Success!</div>
       <div v-if="props.id" class="copy">
         <button class="vf-btn vf-btn-primary spaced-out" v-if="copy" disabled=true>
           Copied
         </button>
         <div v-else-if="notDeleted">
           <button class="vf-btn vf-btn-primary spaced-out" @click="duplicate">
             Copy
           </button>
           <span> </span>
           <button  class="vf-btn vf-btn-danger" @click.prevent="deleteOpp">
             Delete
           </button>
         </div>
       </div>
      <FormElements>

        <HiddenElement name="owner" :value="user.admin && form$.owner ? form$.owner : user.id"/>
        <StaticElement
          name="p_title"
          content="Title"
          tag="p"
        />
         <TextElement
           name="title"
           rules="required"
         />
         <StaticElement
           name="p_description"
           content="Description"
           tag="p"
         />
         <EditorElement
           name="body"
           placeholder="Describe your opportunity here."
           :hide-tools="['attach', 'code']"
         />
         <StaticElement
           name="p_category"
           content="VMS Category"
           tag="p"
         />
         <SelectElement
           name="category"
           :native="false"
           :items="CATEGORY_CODES"
           rules="required"
         />
         <StaticElement
           name="p_project"
           content="Project ID"
           tag="p"
           :conditions="[
            [
              'category',
              'not_in',
              [
                'AT',
                'EV',
              ],
            ],
          ]"
         />
         <TextElement
           name="project_id"
           rules="numeric|between:400,3000"
           :conditions="[
            [
              'category',
              'not_in',
              [
                'AT',
                'EV',
              ],
            ],
          ]"
         />
         <StaticElement
           name="at_category_p"
           content="AT Category"
           tag="p"
           :conditions="[
             ['category', '==', 'AT']
           ]"
         />
         <SelectElement
           name="at_category"
           :native="false"
           :items="AT_CATEGORIES"
           :conditions="[
             ['category', '==', 'AT']
           ]"
         />
         <ToggleElement
           name="anywhere"
           label="This opportunity can be done anywhere."
           :columns="{
             container: 12,
             label: 10,
             wrapper: 12,
           }"
           align="right"
           :default="false"
         />
         <StaticElement
           name="p_location"
           content="Address or Crossroads."
           tag="p"
           :conditions="[
            [
              'anywhere',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <TextElement
           name="location"
           :rules="[
             {
               required: ['anywhere', '!=', true]
             }
           ]"
           :conditions="[
            [
              'anywhere',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <StaticElement
           name="p_city"
           content="City"
           tag="p"
           :conditions="[
            [
              'anywhere',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <SelectElement
           name="city"
           :native="false"
           :items="CITIES"
           :conditions="[
            [
              'anywhere',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <ToggleElement
           name="anytime"
           label="This opportunity can be done anytime."
           :columns="{
             container: 12,
             label: 10,
             wrapper: 12,
           }"
           align="right"
           :default="false"
         />
         <StaticElement
           name="p_start"
           content="Start date and time"
           tag="p"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <DateElement
           name="event_start"
           :date="true"
           :time="true"
           :hour24="false"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
          :rules="[
            {
              required: ['anytime', '!=', true]
            }
          ]"
          @change="(newValue, oldValue, el$) => {
                updateEndTime(newValue, oldValue, el$)
              }"
         />
         <StaticElement
           name="p_end"
           content="End date and time"
           tag="p"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <DateElement
           name="event_end"
           :date="true"
           :time="true"
           :hour24="false"
           :default="defaultEndTime"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
          :rules="[
            {
              required: ['anytime', '!=', true]
            }
          ]"
         />
         <StaticElement
           name="p_recurring_w"
           content="Recurring Weekly"
           description="Repeat this event every week"
           :columns="{
             container: 10,
             label: 12,
             wrapper: 12,
           }"
           tag="p"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
            [
              'recurring_monthly',
              'in',
              [
                null,
                '',
              ],
            ],
          ]"
         />
         <ToggleElement
           name="recurring_weekly"
           :columns="{
             container: 2,
             label: 12,
             wrapper: 12,
           }"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
            [
              'recurring_monthly',
              'in',
              [
                null,
                '',
              ],
            ],
          ]"
           align="right"
           :default="false"
         />
         <StaticElement
           name="p_recurring_m"
           content="Recurring Monthly"
           description="Repeat this the nth [Satur]day of every month"
           :columns="{
             container: 10,
             label: 12,
             wrapper: 12,
           }"
           tag="p"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
            [
              'recurring_weekly',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <TextElement
           name="recurring_monthly"
           :conditions="[
            [
              'anytime',
              'in',
              [
                false,
                null,
              ],
            ],
            [
              'recurring_weekly',
              'in',
              [
                false,
                null,
              ],
            ],
          ]"
         />
         <StaticElement
           name="p_expire"
           content="Expiration date (not required)"
           tag="p"
         />
         <DateElement
           name="expiration_date"
           :date="true"
           :time="true"
           :hour24="false"
           :show-current="false"
         />
         <StaticElement
           name="p_link"
           content="Provide the full URL to sign up or get more information about this opportunity"
           tag="p"
         />
         <TextElement
           name="link"
           :rules="[
            {
              url: ['just_show_up', '!=', true],
            },
            {
              required: ['just_show_up', '!=', true],
            },
           ]"
         />
         <StaticElement
           name="p_show_up"
           content="Can you just show up?"
           description="Check this box if volunteers don't need to RSVP."
           :columns="{
             container: 10,
             label: 12,
             wrapper: 12,
           }"
           tag="p"
         />
         <ToggleElement
           name="just_show_up"
           :columns="{
             container: 2,
             label: 12,
             wrapper: 12,
           }"
           align="right"
           :default="false"
         />

     </FormElements>
     <FormStepsControls v-if="notDeleted"/>
     <div class="help">
       <a href="https://docs.google.com/document/d/1zqQsXDq8cU7HPE-stWppD7BPM8NVLXM18IK7-XABtmE/edit?usp=sharing">Help</a> | 
       <RouterLink to="/">Exit</RouterLink>
     </div>  
     </template>
  </Vueform>
 </template>

 <style media="screen">
  .opportunity-form {
    width: 600px;
    max-width: 100%;
    margin: auto;
  }
  .error {
    color: red;
  }
  .success {
    font-size: 3em;
  }
  .copy {
    text-align: right;
    padding-bottom: 10px;
  }
  .help {
    text-align: right;
    padding: 10px 0;
  }
  .spaced-out {
    margin: 5px;
  }
 </style>
