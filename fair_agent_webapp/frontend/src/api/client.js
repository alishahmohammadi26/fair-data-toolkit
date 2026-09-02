import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const http = axios.create({ baseURL: API_BASE })

export const createAssessment  = (data)        => http.post('/assessments/', data)
export const listAssessments   = ()            => http.get('/assessments/')
export const getAssessment     = (id)          => http.get(`/assessments/${id}`)
export const runAssessment     = (id, apiKey)  => http.post(`/assessments/${id}/run`, { api_key: apiKey })
export const submitSmeReview   = (id, payload) => http.put(`/assessments/${id}/sme`, payload)
export const deleteAssessment  = (id)          => http.delete(`/assessments/${id}`)

/** Returns an EventSource for the SSE progress stream. */
export const streamAssessment = (id) =>
  new EventSource(`${API_BASE}/assessments/${id}/stream`)
