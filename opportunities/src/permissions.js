// Pure permission / presentation helpers shared by the components, kept here
// (free of Vue) so they can be unit-tested directly. The edit rule mirrors the
// backend's _edit_allowed in flask_app/opportunities.py.
import { AT_CATEGORIES } from './utils.js'

export const EXEMPT_CATEGORIES = ['AT', 'EV']

// admins edit anything; AT/EV are open to any coordinator; every other
// opportunity requires a matching (project, category) assignment. Ownership
// grants nothing. Accepts either `assigned_combos` or `assignedCombos`.
export function canEditOpportunity(user, opp) {
  if (!user) return false
  if (user.admin) return true
  const isCoordinator = !!(user.project_coordinator || user.coordinator)
  if (!isCoordinator) return false
  if (EXEMPT_CATEGORIES.includes(opp.category)) return true
  const combos = user.assigned_combos || user.assignedCombos || []
  return combos.includes(`${opp.project_id}::${opp.category}`)
}

// The "Project / Activity" dropdown options, in the order the backend expects:
// AT activity types first, then EV, then project (project, category) combos.
// AT/EV are open to any coordinator; admins see every project combo; a non-admin
// coordinator only sees the combos they're assigned to, so the form never
// offers an option the backend would reject.
export function buildComboItems(projects, user) {
  const items = []
  AT_CATEGORIES.forEach(at => items.push({ value: `AT|${at}`, label: `AT — ${at}` }))
  items.push({ value: 'EV|', label: 'EV — Event' })
  const isAdmin = !!(user && user.admin)
  const assigned = new Set((user && user.assigned_combos) || [])
  ;(projects || []).forEach(p => {
    (p.categories || []).forEach(cat => {
      if (isAdmin || assigned.has(`${p.project_id}::${cat}`)) {
        items.push({ value: `${cat}|${p.project_id}`, label: `${p.project_id} ${p.name} — ${cat}` })
      }
    })
  })
  return items
}

export function userType(user) {
  if (user && user.admin) return 'Admin'
  if (user && user.project_coordinator) return 'Coordinator'
  return 'User'
}

// Admin first, then Coordinator, then plain User.
function typeRank(u) {
  return u.admin ? 0 : (u.project_coordinator ? 1 : 2)
}

// Returns a sorted COPY of `users`. Users who have never logged in always sort
// to the bottom, regardless of direction.
export function sortUsers(users, key, dir) {
  const sign = dir === 'asc' ? 1 : -1
  const arr = [...users]
  arr.sort((a, b) => {
    let av, bv
    switch (key) {
      case 'type':
        av = typeRank(a); bv = typeRank(b); break
      case 'last_login': {
        const aL = a.last_login || '', bL = b.last_login || ''
        if (!aL && !bL) return 0
        if (!aL) return 1
        if (!bL) return -1
        av = aL; bv = bL; break
      }
      case 'projects':
        av = (a.assigned_projects || []).length
        bv = (b.assigned_projects || []).length
        break
      default:
        av = (a.email || '').toLowerCase(); bv = (b.email || '').toLowerCase()
    }
    if (av < bv) return -1 * sign
    if (av > bv) return 1 * sign
    return 0
  })
  return arr
}
