<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAssessment, submitSmeReview } from '../api/client.js'
import ScoreGauge from '../components/ScoreGauge.vue'
import RadarChart from '../components/RadarChart.vue'

const route  = useRoute()
const router = useRouter()
const id     = route.params.id

const assessment = ref(null)
const activeTab  = ref('overview')   // 'overview' | 'sme'
const smePrinciple = ref('F')
const smeLocalScores = ref({})       // indicator_id -> { sme_score, sme_notes, sme_approved }
const approvedBy  = ref('')
const markApproved = ref(false)
const saving  = ref(false)
const saved   = ref(false)
const saveErr = ref(null)

const PRINCIPLE_META = {
  F: { label: 'Findable',      color: '#3B82F6', bg: 'bg-blue-50',    border: 'border-blue-200',   text: 'text-blue-700'  },
  A: { label: 'Accessible',    color: '#10B981', bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
  I: { label: 'Interoperable', color: '#8B5CF6', bg: 'bg-violet-50',  border: 'border-violet-200',  text: 'text-violet-700' },
  R: { label: 'Reusable',      color: '#F59E0B', bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700' },
}

const PRIORITY_STYLE = {
  essential: 'bg-red-100 text-red-700',
  important: 'bg-yellow-100 text-yellow-700',
  useful:    'bg-green-100 text-green-700',
}

const scoreLabel = (s) => ['✗ 0 — Not impl.', '△ 1 — Partial', '◎ 2 — Mostly', '✓ 3 — Full'][s] ?? '—'
const scoreClass = (s) => [
  'text-red-600 bg-red-50',
  'text-amber-600 bg-amber-50',
  'text-blue-600 bg-blue-50',
  'text-emerald-600 bg-emerald-50',
][s] ?? 'text-gray-400 bg-gray-50'

const overallColor = (s) => s >= 70 ? '#10B981' : s >= 40 ? '#F59E0B' : '#EF4444'

const principleScores = computed(() => assessment.value ? {
  F: assessment.value.f_score ?? 0,
  A: assessment.value.a_score ?? 0,
  I: assessment.value.i_score ?? 0,
  R: assessment.value.r_score ?? 0,
} : { F: 0, A: 0, I: 0, R: 0 })

const essentialGaps = computed(() => {
  if (!assessment.value?.scores) return []
  return assessment.value.scores.filter(s => s.priority === 'essential' && s.final_score < 3)
})

const smeTabScores = computed(() =>
  (assessment.value?.scores ?? []).filter(s => s.principle === smePrinciple.value)
)

const smeReviewedCount = computed(() =>
  Object.values(smeLocalScores.value).filter(s => s.sme_approved).length
)

onMounted(async () => {
  const res = await getAssessment(id)
  assessment.value = res.data
  approvedBy.value = res.data.sme_approved_by ?? ''
  markApproved.value = res.data.sme_review_status === 'approved'

  // Initialise local SME state from DB values
  for (const s of res.data.scores) {
    smeLocalScores.value[s.indicator_id] = {
      sme_score:    s.sme_score,
      sme_notes:    s.sme_notes ?? '',
      sme_approved: s.sme_approved,
    }
  }
})

async function saveSme() {
  saving.value = true
  saved.value  = false
  saveErr.value = null
  try {
    const overrides = Object.entries(smeLocalScores.value).map(([indicator_id, v]) => ({
      indicator_id,
      sme_score:    v.sme_score,
      sme_notes:    v.sme_notes || null,
      sme_approved: v.sme_approved,
    }))
    const res = await submitSmeReview(id, {
      overrides,
      approved_by:   approvedBy.value || null,
      mark_approved: markApproved.value,
    })
    assessment.value = res.data
    saved.value = true
  } catch (e) {
    saveErr.value = e.response?.data?.detail ?? 'Save failed'
  } finally {
    saving.value = false
  }
}

function approveAll() {
  for (const key in smeLocalScores.value) {
    smeLocalScores.value[key].sme_approved = true
  }
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(assessment.value, null, 2)], { type: 'application/json' })
  const a    = document.createElement('a')
  a.href     = URL.createObjectURL(blob)
  a.download = `fair_assessment_${assessment.value.dataset_id}.json`
  a.click()
}
</script>

<template>
  <div v-if="assessment" class="max-w-5xl mx-auto px-4 py-8">

    <!-- Header -->
    <div class="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div class="flex items-center gap-3">
        <button @click="router.push('/')" class="text-gray-400 hover:text-gray-600 text-xl">←</button>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">{{ assessment.dataset_id }}</h1>
          <p class="text-xs text-gray-400 mt-0.5">
            {{ assessment.assessed_by || 'Unknown' }} · {{ assessment.llm_model }}
            <span :class="[
              'ml-2 px-1.5 py-0.5 rounded text-xs font-medium',
              assessment.sme_review_status === 'approved' ? 'bg-emerald-100 text-emerald-700' :
              assessment.sme_review_status === 'in_progress' ? 'bg-amber-100 text-amber-700' :
              'bg-gray-100 text-gray-500'
            ]">
              SME: {{ { not_started: 'Not reviewed', in_progress: 'In progress', approved: 'Approved' }[assessment.sme_review_status] }}
            </span>
          </p>
        </div>
      </div>
      <div class="flex gap-2">
        <button @click="downloadJson"
          class="text-sm px-3 py-1.5 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50">
          ↓ JSON
        </button>
        <button @click="router.push({ name: 'run', params: { id } })"
          class="text-sm px-3 py-1.5 border border-indigo-200 text-indigo-600 rounded-lg hover:bg-indigo-50">
          ↺ Re-run
        </button>
      </div>
    </div>

    <!-- Score gauges -->
    <div class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6 mb-6">
      <div class="flex flex-wrap justify-around gap-6">
        <ScoreGauge :score="assessment.overall_score ?? 0" label="Overall"
          :color="overallColor(assessment.overall_score ?? 0)" :size="130" />
        <ScoreGauge :score="assessment.f_score ?? 0" label="Findable"      color="#3B82F6" />
        <ScoreGauge :score="assessment.a_score ?? 0" label="Accessible"    color="#10B981" />
        <ScoreGauge :score="assessment.i_score ?? 0" label="Interoperable" color="#8B5CF6" />
        <ScoreGauge :score="assessment.r_score ?? 0" label="Reusable"      color="#F59E0B" />
      </div>
    </div>

    <!-- Principle bars -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      <div v-for="[p, meta] in Object.entries(PRINCIPLE_META)" :key="p"
        :class="['rounded-xl border p-4', meta.bg, meta.border]">
        <div :class="['text-2xl font-bold', meta.text]">{{ principleScores[p] }}%</div>
        <div class="text-xs font-medium text-gray-600 mt-0.5">{{ meta.label }}</div>
        <div class="mt-2 h-1.5 bg-white/60 rounded-full overflow-hidden">
          <div class="h-full rounded-full transition-all"
            :style="`width:${principleScores[p]}%;background:${meta.color}`"></div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 mb-4 border-b border-gray-200">
      <button v-for="t in ['overview', 'sme']" :key="t" @click="activeTab = t"
        :class="['px-4 py-2 text-sm font-medium transition-colors',
          activeTab === t
            ? 'border-b-2 border-indigo-500 text-indigo-600'
            : 'text-gray-500 hover:text-gray-700']">
        {{ t === 'overview' ? '📊 Overview' : '🧑‍🔬 SME Review' }}
        <span v-if="t === 'sme' && smeReviewedCount > 0"
          class="ml-1 text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">
          {{ smeReviewedCount }}/{{ assessment.scores.length }}
        </span>
      </button>
    </div>

    <!-- ────────────── OVERVIEW TAB ────────────── -->
    <template v-if="activeTab === 'overview'">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <!-- Radar chart -->
        <div class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6 flex flex-col items-center">
          <h3 class="text-sm font-semibold text-gray-600 mb-4">FAIR Radar</h3>
          <RadarChart :scores="principleScores" />
        </div>

        <!-- Essential gaps -->
        <div class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
          <h3 class="text-sm font-semibold text-gray-600 mb-3">
            Essential Gaps
            <span class="ml-2 text-xs bg-red-50 text-red-500 px-2 py-0.5 rounded-full">
              {{ essentialGaps.length }} unmet
            </span>
          </h3>
          <div v-if="essentialGaps.length" class="space-y-2 max-h-64 overflow-y-auto">
            <div v-for="gap in essentialGaps" :key="gap.indicator_id"
              class="flex items-start gap-2 p-2 bg-red-50 border border-red-100 rounded-lg text-xs">
              <span class="text-red-400 shrink-0 mt-0.5">✗</span>
              <div>
                <span :class="['font-mono font-bold mr-1.5 px-1 rounded text-xs',
                  PRINCIPLE_META[gap.principle]?.text, PRINCIPLE_META[gap.principle]?.bg]">
                  {{ gap.indicator_id }}
                </span>
                <span class="text-gray-700">{{ gap.indicator_name }}</span>
                <div class="text-gray-400 mt-0.5">Final score: {{ gap.final_score }}/3</div>
              </div>
            </div>
          </div>
          <div v-else class="text-emerald-600 text-sm font-medium">✓ All essential indicators compliant.</div>
        </div>
      </div>

      <!-- Full scorecard table -->
      <div class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
        <h3 class="text-sm font-semibold text-gray-600 mb-4">All Indicator Scores</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-gray-100 text-left text-gray-400 uppercase tracking-wide">
                <th class="pb-2 pr-3 w-32">ID</th>
                <th class="pb-2 pr-3">Indicator</th>
                <th class="pb-2 pr-3 w-20 text-center">Auto</th>
                <th class="pb-2 pr-3 w-20 text-center">SME</th>
                <th class="pb-2 w-20 text-center">Final</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="s in assessment.scores" :key="s.indicator_id" class="hover:bg-gray-50">
                <td class="py-1.5 pr-3">
                  <span :class="['font-mono font-bold px-1.5 py-0.5 rounded text-xs',
                    PRINCIPLE_META[s.principle]?.text, PRINCIPLE_META[s.principle]?.bg]">
                    {{ s.indicator_id }}
                  </span>
                </td>
                <td class="py-1.5 pr-3 text-gray-700">{{ s.indicator_name }}</td>
                <td class="py-1.5 pr-3 text-center">
                  <span :class="['px-1.5 py-0.5 rounded font-bold', scoreClass(s.auto_score)]">
                    {{ s.auto_score }}
                  </span>
                </td>
                <td class="py-1.5 pr-3 text-center text-gray-400">
                  {{ s.sme_score != null ? s.sme_score : '—' }}
                </td>
                <td class="py-1.5 text-center">
                  <span :class="['px-1.5 py-0.5 rounded font-bold', scoreClass(s.final_score)]">
                    {{ s.final_score }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ────────────── SME REVIEW TAB ────────────── -->
    <template v-else>
      <div class="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">

        <!-- Principle tabs -->
        <div class="flex gap-1 mb-5 flex-wrap">
          <button v-for="[p, meta] in Object.entries(PRINCIPLE_META)" :key="p"
            @click="smePrinciple = p"
            :class="['px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors',
              smePrinciple === p ? `${meta.bg} ${meta.text} ${meta.border} border` : 'bg-gray-100 text-gray-500 hover:bg-gray-200']">
            {{ p }} — {{ meta.label }}
          </button>
        </div>

        <!-- Per-indicator rows -->
        <div class="space-y-3">
          <div v-for="s in smeTabScores" :key="s.indicator_id"
            :class="['border rounded-xl p-4 transition-colors',
              smeLocalScores[s.indicator_id]?.sme_approved ? 'border-emerald-200 bg-emerald-50/30' : 'border-gray-200']">

            <!-- Row header -->
            <div class="flex flex-wrap items-start gap-2 mb-3">
              <span :class="['font-mono font-bold text-xs px-1.5 py-0.5 rounded',
                PRINCIPLE_META[s.principle]?.text, PRINCIPLE_META[s.principle]?.bg]">
                {{ s.indicator_id }}
              </span>
              <span :class="['text-xs px-1.5 py-0.5 rounded font-medium', PRIORITY_STYLE[s.priority]]">
                {{ s.priority }}
              </span>
              <span class="text-sm text-gray-800 font-medium">{{ s.indicator_name }}</span>
              <span class="ml-auto flex items-center gap-1">
                <input type="checkbox" :id="`apv-${s.indicator_id}`"
                  v-model="smeLocalScores[s.indicator_id].sme_approved"
                  class="rounded accent-emerald-500" />
                <label :for="`apv-${s.indicator_id}`" class="text-xs text-gray-500 cursor-pointer">
                  Approved
                </label>
              </span>
            </div>

            <!-- Agent output -->
            <div class="mb-3 p-2 bg-gray-50 rounded-lg text-xs">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-gray-400 font-medium">Agent score:</span>
                <span :class="['px-1.5 py-0.5 rounded font-bold', scoreClass(s.auto_score)]">
                  {{ s.auto_score }}/3 — {{ scoreLabel(s.auto_score) }}
                </span>
              </div>
              <details>
                <summary class="cursor-pointer text-gray-400 hover:text-gray-600">Evidence &amp; reasoning</summary>
                <p class="mt-1 text-gray-600 whitespace-pre-wrap">{{ s.auto_evidence_summary }}</p>
                <p class="mt-1 text-gray-500 italic">{{ s.auto_reasoning }}</p>
              </details>
            </div>

            <!-- SME override controls -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">SME Score Override</label>
                <select v-model="smeLocalScores[s.indicator_id].sme_score"
                  class="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  <option :value="null">— Keep agent score ({{ s.auto_score }})</option>
                  <option :value="0">0 — Not implemented</option>
                  <option :value="1">1 — Partial / under consideration</option>
                  <option :value="2">2 — Mostly compliant</option>
                  <option :value="3">3 — Fully implemented</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">SME Notes</label>
                <input v-model="smeLocalScores[s.indicator_id].sme_notes"
                  placeholder="Add expert context…"
                  class="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300" />
              </div>
            </div>
          </div>
        </div>

        <!-- Save controls -->
        <div class="mt-6 pt-5 border-t border-gray-100 flex flex-wrap items-center gap-4">
          <div class="flex-1 min-w-48">
            <label class="block text-xs font-medium text-gray-500 mb-1">Approved By</label>
            <input v-model="approvedBy" placeholder="Reviewer name"
              class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
          </div>
          <div class="flex items-center gap-2">
            <input id="markApproved" type="checkbox" v-model="markApproved" class="rounded accent-emerald-500" />
            <label for="markApproved" class="text-sm text-gray-600 cursor-pointer">Mark review as approved</label>
          </div>
          <button @click="approveAll"
            class="text-sm px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">
            ✓ Approve All
          </button>
          <div class="flex items-center gap-2">
            <button @click="saveSme" :disabled="saving"
              class="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors">
              {{ saving ? 'Saving…' : 'Save SME Review' }}
            </button>
            <transition name="fade">
              <span v-if="saved" class="text-xs text-emerald-600 font-medium">✓ Saved</span>
            </transition>
            <span v-if="saveErr" class="text-xs text-red-500">{{ saveErr }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>

  <div v-else class="text-center py-20 text-gray-400">Loading assessment…</div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.5s; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }
</style>
