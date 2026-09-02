<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAssessment, runAssessment, streamAssessment } from '../api/client.js'

const route  = useRoute()
const router = useRouter()
const id     = route.params.id

const assessment = ref(null)
const apiKey     = ref('')
const running    = ref(false)
const error      = ref(null)
const pct        = ref(0)
const log        = ref([])
const completed  = ref(new Set())
let   source     = null

const NODES = [
  { key: 'discover',       label: 'Discover',   icon: '🔍' },
  { key: 'assess_F',       label: 'Findable',   icon: '🔵' },
  { key: 'assess_A',       label: 'Accessible', icon: '🟢' },
  { key: 'assess_I',       label: 'Interoperable', icon: '🟣' },
  { key: 'assess_R',       label: 'Reusable',   icon: '🟡' },
  { key: 'compile_report', label: 'Report',     icon: '📋' },
]

onMounted(async () => {
  try {
    const res    = await getAssessment(id)
    assessment.value = res.data
    // If still running (e.g. page reload), reconnect SSE
    if (res.data.status === 'running') connectSSE()
    if (res.data.status === 'complete') router.replace({ name: 'result', params: { id } })
  } catch {
    error.value = 'Could not load assessment'
  }
})

onBeforeUnmount(() => source?.close())

async function start() {
  if (!apiKey.value.trim()) return
  error.value = null
  log.value   = []
  pct.value   = 0
  completed.value = new Set()
  running.value   = true

  try {
    await runAssessment(id, apiKey.value.trim())
    connectSSE()
  } catch (e) {
    running.value = false
    error.value   = e.response?.data?.detail ?? 'Failed to start run'
  }
}

function connectSSE() {
  source = streamAssessment(id)
  source.onmessage = (e) => {
    const evt = JSON.parse(e.data)
    if (evt.type === 'progress') {
      pct.value = evt.pct ?? pct.value
      log.value.push(evt.message)
      completed.value = new Set([...completed.value, evt.node])
    } else if (evt.type === 'done') {
      pct.value     = 100
      running.value = false
      source?.close()
      setTimeout(() => router.push({ name: 'result', params: { id } }), 800)
    } else if (evt.type === 'error') {
      running.value = false
      error.value   = evt.message
      source?.close()
    }
  }
  source.onerror = () => {
    if (running.value) {
      error.value   = 'Connection to server lost. Check the API is running.'
      running.value = false
    }
    source?.close()
  }
}

function nodeState(key) {
  if (completed.value.has(key)) return 'done'
  // "active" = last node not yet done, but run is in progress
  const idx     = NODES.findIndex(n => n.key === key)
  const doneIdx = NODES.findLastIndex(n => completed.value.has(n.key))
  if (running.value && idx === doneIdx + 1) return 'active'
  return 'pending'
}
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 py-10">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button @click="router.push('/')" class="text-gray-400 hover:text-gray-600 text-xl">←</button>
      <div v-if="assessment">
        <h1 class="text-xl font-bold text-gray-900">{{ assessment.dataset_id }}</h1>
        <p class="text-xs text-gray-400">{{ assessment.catalog_url }} · {{ assessment.llm_model }}</p>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-5 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">
      {{ error }}
    </div>

    <!-- API Key + Run -->
    <div v-if="!running" class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6 mb-6">
      <h2 class="font-semibold text-gray-800 mb-4">Configure LLM</h2>
      <div class="space-y-3">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">
            OpenAI API Key <span class="text-red-400">*</span>
          </label>
          <input
            v-model="apiKey"
            type="password"
            placeholder="sk-…"
            class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <p class="text-xs text-gray-400 mt-1">
            Your key is used only for this run and is never stored.
          </p>
        </div>

        <div class="p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-700">
          <p class="font-semibold">⚠️ Before running:</p>
          <ul class="mt-1 ml-3 list-disc space-y-0.5">
            <li>Mock catalog must be running on <code>{{ assessment?.catalog_url }}</code></li>
            <li>LLM model: <strong>{{ assessment?.llm_model }}</strong></li>
            <li>Dataset: <strong>{{ assessment?.dataset_id }}</strong></li>
            <li>Assessment takes ~30–90 seconds</li>
          </ul>
        </div>

        <button
          @click="start"
          :disabled="!apiKey.trim()"
          class="w-full bg-indigo-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ▶ Run FAIR Assessment
        </button>
      </div>
    </div>

    <!-- Progress pipeline -->
    <div v-if="running || completed.size > 0" class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-gray-800">Agent Progress</h2>
        <span class="text-sm font-bold text-indigo-600">{{ pct }}%</span>
      </div>

      <!-- Progress bar -->
      <div class="h-2 bg-gray-100 rounded-full overflow-hidden mb-6">
        <div
          class="h-full bg-indigo-500 rounded-full transition-all duration-500"
          :style="`width: ${pct}%`"
        ></div>
      </div>

      <!-- Step nodes -->
      <div class="flex items-center justify-between">
        <template v-for="(node, idx) in NODES" :key="node.key">
          <div class="flex flex-col items-center gap-1 flex-1">
            <div :class="[
              'w-9 h-9 rounded-full flex items-center justify-center text-sm border-2 transition-all',
              nodeState(node.key) === 'done'   ? 'bg-emerald-100 border-emerald-400 text-emerald-700' :
              nodeState(node.key) === 'active' ? 'bg-indigo-100 border-indigo-400 text-indigo-700 pulse' :
                                                  'bg-gray-100 border-gray-200 text-gray-400',
            ]">
              {{ nodeState(node.key) === 'done' ? '✓' : node.icon }}
            </div>
            <span class="text-xs text-center text-gray-500 leading-tight max-w-[60px]">{{ node.label }}</span>
          </div>
          <div v-if="idx < NODES.length - 1"
            :class="['flex-1 h-0.5 mb-5', completed.value?.has(NODES[idx + 1]?.key) || nodeState(NODES[idx + 1]?.key) !== 'pending' ? 'bg-emerald-300' : 'bg-gray-200']">
          </div>
        </template>
      </div>
    </div>

    <!-- Log -->
    <div v-if="log.length" class="bg-gray-900 rounded-2xl p-4 font-mono text-xs">
      <p class="text-gray-500 mb-2 uppercase tracking-widest text-xs">Agent Log</p>
      <div class="space-y-1 max-h-48 overflow-y-auto">
        <p v-for="(line, i) in log" :key="i" class="text-emerald-400">
          <span class="text-gray-500 mr-2">[{{ String(i + 1).padStart(2, '0') }}]</span>{{ line }}
        </p>
        <p v-if="running" class="text-gray-400 animate-pulse">▌</p>
      </div>
    </div>

    <!-- Done redirect message -->
    <div v-if="pct === 100" class="mt-4 text-center text-sm text-emerald-600 font-medium">
      ✓ Assessment complete — redirecting to results…
    </div>
  </div>
</template>
