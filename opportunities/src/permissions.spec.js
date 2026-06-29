import { describe, it, expect } from 'vitest'
import { canEditOpportunity, buildComboItems, userType, sortUsers } from './permissions.js'

describe('canEditOpportunity', () => {
  const admin = { admin: 1 }
  const coord = { project_coordinator: 1, assigned_combos: ['410::RM'] }
  const plain = { admin: 0, project_coordinator: 0 }

  it('admins may edit anything', () => {
    expect(canEditOpportunity(admin, { category: 'RM', project_id: '999' })).toBe(true)
  })

  it('a coordinator may edit a combo they are assigned to', () => {
    expect(canEditOpportunity(coord, { category: 'RM', project_id: '410' })).toBe(true)
  })

  it('assignment is category-specific', () => {
    expect(canEditOpportunity(coord, { category: 'NPA', project_id: '410' })).toBe(false)
  })

  it('a coordinator may not edit an unassigned project', () => {
    expect(canEditOpportunity(coord, { category: 'RM', project_id: '999' })).toBe(false)
  })

  it('AT/EV are editable by any coordinator', () => {
    expect(canEditOpportunity(coord, { category: 'AT', project_id: 'TMN Tuesday' })).toBe(true)
    expect(canEditOpportunity(coord, { category: 'EV', project_id: '' })).toBe(true)
  })

  it('AT/EV still require coordinator (or admin)', () => {
    expect(canEditOpportunity(plain, { category: 'AT', project_id: 'x' })).toBe(false)
  })

  it('non-coordinator, non-admin is denied', () => {
    expect(canEditOpportunity(plain, { category: 'RM', project_id: '410' })).toBe(false)
  })

  it('accepts the assignedCombos prop spelling too', () => {
    const u = { coordinator: true, assignedCombos: ['410::RM'] }
    expect(canEditOpportunity(u, { category: 'RM', project_id: '410' })).toBe(true)
  })

  it('null user is denied', () => {
    expect(canEditOpportunity(null, { category: 'AT' })).toBe(false)
  })
})

describe('buildComboItems', () => {
  const projects = [
    { project_id: '410', name: 'Trails', categories: ['RM', 'NPA'] },
    { project_id: '999', name: 'Other', categories: ['PO'] },
  ]

  it('admins see AT, EV, and every project combo', () => {
    const items = buildComboItems(projects, { admin: 1 })
    const values = items.map(i => i.value)
    expect(values).toContain('RM|410')
    expect(values).toContain('NPA|410')
    expect(values).toContain('PO|999')
    expect(values.filter(v => v.startsWith('AT|')).length).toBeGreaterThan(0)
    expect(values).toContain('EV|')
  })

  it('a coordinator only sees AT, EV, and their assigned project combos', () => {
    const items = buildComboItems(projects, { project_coordinator: 1, assigned_combos: ['410::RM'] })
    const values = items.map(i => i.value)
    expect(values).toContain('RM|410')      // assigned
    expect(values).not.toContain('NPA|410') // not assigned
    expect(values).not.toContain('PO|999')  // not assigned
    expect(values).toContain('EV|')         // always
  })

  it('orders AT first, then EV, then project combos', () => {
    const items = buildComboItems(projects, { admin: 1 })
    const firstProjectIdx = items.findIndex(i => /^(RM|NPA|PO)\|/.test(i.value))
    const evIdx = items.findIndex(i => i.value === 'EV|')
    const firstAtIdx = items.findIndex(i => i.value.startsWith('AT|'))
    expect(firstAtIdx).toBe(0)
    expect(evIdx).toBeLessThan(firstProjectIdx)
  })
})

describe('userType', () => {
  it('ranks admin over coordinator over user', () => {
    expect(userType({ admin: 1, project_coordinator: 1 })).toBe('Admin')
    expect(userType({ project_coordinator: 1 })).toBe('Coordinator')
    expect(userType({})).toBe('User')
  })
})

describe('sortUsers', () => {
  const users = [
    { email: 'b@x.org', admin: 0, project_coordinator: 1, last_login: '2026-06-01 10:00', assigned_projects: [1, 2] },
    { email: 'a@x.org', admin: 1, project_coordinator: 0, last_login: null, assigned_projects: [] },
    { email: 'c@x.org', admin: 0, project_coordinator: 0, last_login: '2026-06-10 09:00', assigned_projects: [1] },
  ]

  it('sorts by email ascending and descending', () => {
    expect(sortUsers(users, 'email', 'asc').map(u => u.email)).toEqual(['a@x.org', 'b@x.org', 'c@x.org'])
    expect(sortUsers(users, 'email', 'desc').map(u => u.email)).toEqual(['c@x.org', 'b@x.org', 'a@x.org'])
  })

  it('sorts by type (admin, coordinator, user)', () => {
    expect(sortUsers(users, 'type', 'asc').map(u => u.email)).toEqual(['a@x.org', 'b@x.org', 'c@x.org'])
  })

  it('always sorts never-logged-in users last, both directions', () => {
    expect(sortUsers(users, 'last_login', 'asc').at(-1).email).toBe('a@x.org')
    expect(sortUsers(users, 'last_login', 'desc').at(-1).email).toBe('a@x.org')
  })

  it('sorts by assigned-project count', () => {
    expect(sortUsers(users, 'projects', 'desc')[0].email).toBe('b@x.org')
  })

  it('does not mutate the input array', () => {
    const copy = [...users]
    sortUsers(users, 'email', 'desc')
    expect(users).toEqual(copy)
  })
})
