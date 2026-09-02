<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listAssessments, createAssessment, deleteAssessment } from '../api/client.js'

const router      = useRouter()
const assessments = ref([])
const loading     = ref(false)
const creating    = ref(false)
const error       = ref(null)

const form = ref({
  dataset_id:  '',
  catalog_url: 'http://localhost:9321',
  llm_model:   'gpt-4o-mini',
  assessed_by: '',
  notes:       '',
})

const STATUS_STYLES = {
  pending:  'bg-gray-100 text-gray-600',
  running:  'bg-blue-100 text-blue-700',
  complete: 'bg-emerald-100 text-emerald-700',
  error:    'bg-red-100 text-red-600',
}

const SME_STYLES = {
  not_started: 'text-gray-400',
  in_progress: 'text-amber-600',
  approved:    'text-emerald-600',
}

const SME_LABELS = {
  not_started: '○ Not reviewed',
  in_progress: '◑ In progress',
  approved:    '✓ Approved',
}

const scoreColor = (s) => {
  if (s == null) return 'text-gray-400'
  if (s >= 70)   return 'text-emerald-600'
  if (s >= 40)   return 'text-amber-600'
  return 'text-red-500'
}

onMounted(fetchList)

async function fetchList() {
  loading.value = true
  error.value   = null
  try {
    const res      = await listAssessments()
    assessments.value = res.data
  } catch {
    error.value = 'Could not reach the API. Is the backend running on port 8080?'
  } finally {
    loading.value = false
  }
}

async function startNew() {
  if (!form.value.dataset_id || !form.value.catalog_url) return
  creating.value = true
  try {
    const res = await createAssessment(form.value)
    router.push({ name: 'run', params: { id: res.data.id } })
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Failed to create assessment'
  } finally {
    creating.value = false
  }
}

async function remove(id) {
  await deleteAssessment(id)
  assessments.value = assessments.value.filter(a => a.id !== id)
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-10">
    <!-- Hero -->
    <div class="text-center mb-10">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">⚗️ FAIR Studio</h1>
      <p class="text-gray-500 max-w-xl mx-auto text-sm">
        AI-powered FAIR Data Maturity Assessment. Connect your data catalog, provide an LLM API key,
        and let the agent score all 20 RDA indicators — then review and approve with your expert judgement.
      </p>
    </div>

    <!-- Error banner -->
    <div v-if="error" class="mb-6 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">
      {{ error }}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <!-- ── New assessment form ─────────────────────── -->
      <div class="lg:col-span-2 bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
        <h2 class="font-semibold text-gray-800 mb-4 text-sm uppercase tracking-wide">New Assessment</h2>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Dataset ID <span class="text-red-400">*</span></label>
            <input v-model="form.dataset_id" placeholder="e.g. STUDY-INV-001"
              class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Catalog API URL <span class="text-red-400">*</span></label>
            <input v-model="form.catalog_url" placeholder="http://localhost:9321"
              class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
            <p class="text-xs text-gray-400 mt-1">Base URL of your FAIR data catalog REST API</p>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">LLM Model</label>
            <select v-model="form.llm_model"
              class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
              <option>gpt-4o-mini</option>
              <option>gpt-4o</option>
              <option>gpt-4-turbo</option>
              <option>gpt-3.5-turbo</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Assessed By</label>
            <input v-model="form.assessed_by" placeholder="Your name / team"
              class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Notes</label>
            <textarea v-model="form.notes" rows="2" placeholder="Optional context…"
              class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300"></textarea>
          </div>

          <button @click="startNew" :disabled="creating || !form.dataset_id || !form.catalog_url"
            class="w-full bg-indigo-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {{ creating ? 'Creating…' : '→ Configure & Run Assessment' }}
          </button>
        </div>

        <!-- Catalog reference hint -->
        <div class="mt-5 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
          <p class="font-semibold mb-1">📋 Required catalog endpoints:</p>
          <code class="block">/metadata  /schema  /records</code>
          <code class="block">/lineage   /access</code>
          <p class="mt-1 text-blue-500">Use the mock catalog on port 9321 to test.</p>
        </div>
      </div>

      <!-- ── Recent assessments table ───────────────── -->
      <div class="lg:col-span-3 bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold text-gray-800 text-sm uppercase tracking-wide">Recent Assessments</h2>
          <button @click="fetchList" class="text-xs text-indigo-600 hover:text-indigo-800">↻ Refresh</button>
        </div>

        <div v-if="loading" class="text-center py-10 text-gray-400 text-sm">Loading…</div>

        <div v-else-if="!assessments.length" class="text-center py-10 text-gray-400 text-sm">
          No assessments yet. Create one to get started.
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wide">
                <th class="pb-2 pr-3">Dataset</th>
                <th class="pb-2 pr-3">Status</th>
                <th class="pb-2 pr-3">Score</th>
                <th class="pb-2 pr-3">SME</th>
                <th class="pb-2"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="a in assessments" :key="a.id" class="hover:bg-gray-50 transition-colors">
                <td class="py-2 pr-3">
                  <div class="font-medium text-gray-800 text-xs">{{ a.dataset_id }}</div>
                  <div class="text-gray-400 text-xs">{{ a.assessed_by || '—' }} · {{ a.llm_model }}</div>
                </td>
                <td class="py-2 pr-3">
                  <span :class="['px-2 py-0.5 rounded-full text-xs font-medium', STATUS_STYLES[a.status] ?? 'bg-gray-100 text-gray-500']">
                    {{ a.status }}
                  </span>
                </td>
                <td class="py-2 pr-3">
                  <span v-if="a.overall_score != null" :class="['font-bold text-sm', scoreColor(a.overall_score)]">
                    {{ a.overall_score }}%
                  </span>
                  <span v-else class="text-gray-300 text-xs">—</span>
                </td>
                <td class="py-2 pr-3">
                  <span :class="['text-xs font-medium', SME_STYLES[a.sme_review_status]]">
                    {{ SME_LABELS[a.sme_review_status] }}
                  </span>
                </td>
                <td class="py-2">
                  <div class="flex items-center gap-1.5">
                    <button v-if="a.status === 'pending' || a.status === 'error'"
                      @click="router.push({ name: 'run', params: { id: a.id } })"
                      class="text-xs px-2 py-1 bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100">
                      Run
                    </button>
                    <button v-if="a.status === 'complete'"
                      @click="router.push({ name: 'result', params: { id: a.id } })"
                      class="text-xs px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100">
                      View
                    </button>
                    <button v-if="a.status === 'running'"
                      @click="router.push({ name: 'run', params: { id: a.id } })"
                      class="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
                      Live
                    </button>
                    <button @click="remove(a.id)"
                      class="text-xs px-2 py-1 bg-gray-50 text-gray-400 rounded hover:bg-red-50 hover:text-red-500">
                      ✕
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
