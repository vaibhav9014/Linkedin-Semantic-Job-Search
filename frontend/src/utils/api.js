/**
 * API client for the FastAPI backend.
 * Centralized here so the base URL only needs to change in one place
 * (e.g. when moving from localhost to a deployed backend URL).
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export class ApiError extends Error {
  constructor(message, status, code = null) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      credentials: 'include',
      ...options,
    })
  } catch {
    throw new ApiError("Can't reach the matching server. Is the backend running?", 0)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new ApiError(
      typeof detail === 'string' ? detail : detail?.message || 'The request failed.',
      response.status,
      detail?.code || null
    )
  }
  return response.json()
}

/**
 * Upload a resume PDF and get ranked job matches.
 * @param {File} file - The PDF file object
 * @param {number} topK - Number of results to return
 */
export async function matchResume(file, topK = 10) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('top_k', String(topK))
  return request('/match', { method: 'POST', body: formData })
}

export async function checkHealth() {
  try {
    return await request('/health')
  } catch {
    return null
  }
}

export async function getLinkedInProfile() {
  try {
    const result = await request('/auth/me')
    return result
  } catch (error) {
    if (error.status === 401) return null
    throw error
  }
}

export function beginLinkedInSignIn() {
  window.location.assign(`${API_BASE}/auth/linkedin/login`)
}

export function beginLinkedInSharePermission() {
  window.location.assign(`${API_BASE}/auth/linkedin/share-permission`)
}

export async function shareJobMatch(job, commentary) {
  return request('/linkedin/share', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: job.title,
      company: job.company,
      apply_url: job.apply_url,
      source: job.source,
      commentary,
    }),
  })
}
