import moment from 'moment'

export const CATEGORY_CODES = {
  'PO': 'Public Outreach',
  'DO': 'Direct Outreach',
  'TG': 'Technical Guidance',
  'RM': 'Natural Resource Management',
  'NPA': 'Nature/Public Access',
  'CB': 'Chapter Business',
  'FR': 'Field Research',
  'AT': 'Advanced Training',
  'EV': 'Event',
}

export const CITIES = [
  "Austin", 
  "Buda",
  "Canyon Lake",
  "Driftwood",
  "Dripping Springs", 
  "Georgetown",
  "Johnson City", 
  "Kyle",
  "Lockhart",
  "Manchaca",
  "Marble Falls",
  "New Braunfels",
  "Round Mountain",
  "San Antonio",      
  "San Marcos",          
  "Wimberley",   
  "Other", 
]

export const AT_CATEGORIES = [
  'Chapter Meeting-Hays County',
  'Interactive Webinars',
  'Lecture Series',
  'Project Specific Training',
  'Single Presentations & Interpretive Field Trips/Hikes',
  'TMN Tuesday',
  'TX Waters Certification Training',
  'TxMN Annual Meeting',
  'VMS Training',
]

function formatDateTime(unformattedDt) {
  const dt = moment(unformattedDt)
  return dt.format('LT') === '12:00 AM' ?
    '' : dt.format('LT')
}

export function formatDateDisplay(opp) {
  if (opp.anytime) {
    return 'Anytime'
  } else {
    const time = formatDateTime(opp.event_start)
    return opp.event_end ? time.concat(' - ', moment(opp.event_end).format('LT')) : time
  }
}

function formatModalDateTime(unformattedDt) {
  const dt = moment(unformattedDt)
  return dt.format('LT') === '12:00 AM' ?
    dt.format("dddd, MMMM Do") : dt.format("dddd, MMMM Do, h:mm a")
}

export function formatModalDateDisplay(opp) {
  if (opp.anytime) {
    return 'Anytime'
  } else {
    const time = formatModalDateTime(opp.event_start)
    return opp.event_end ? time.concat(' - ', moment(opp.event_end).format('LT')) : time
  }
}

export function findDefaultEndTime(unformattedDt) {
  const dt = moment(unformattedDt)
  return dt.add(1, 'hour').format('YYYY-MM-DD hh:mm a')
}

export function getCategory(category) {
  return CATEGORY_CODES[category]
}

export const DOMAIN = window.location.port === "5173" ?
                        "http://localhost:5000" :
                        ""
