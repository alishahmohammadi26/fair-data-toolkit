<script setup>
import { computed } from 'vue'

/**
 * Pure-SVG radar chart for 4-axis FAIR scores.
 * Axes: F=top, A=right, I=bottom, R=left  (clockwise from 12 o'clock).
 */
const props = defineProps({
  scores: {
    type: Object,
    default: () => ({ F: 0, A: 0, I: 0, R: 0 }),
  },
  size: { type: Number, default: 220 },
})

const CX   = computed(() => props.size / 2)
const CY   = computed(() => props.size / 2)
const R    = computed(() => props.size * 0.38)  // max radius

const AXES = [
  { key: 'F', label: 'Findable',      angle: -90, color: '#3B82F6' },
  { key: 'A', label: 'Accessible',    angle:   0, color: '#10B981' },
  { key: 'I', label: 'Interoperable', angle:  90, color: '#8B5CF6' },
  { key: 'R', label: 'Reusable',      angle: 180, color: '#F59E0B' },
]

function polar(angleDeg, r) {
  const rad = (angleDeg * Math.PI) / 180
  return {
    x: CX.value + r * Math.cos(rad),
    y: CY.value + r * Math.sin(rad),
  }
}

// Background rings at 25%, 50%, 75%, 100%
const rings = computed(() =>
  [25, 50, 75, 100].map(pct => {
    const r = (R.value * pct) / 100
    const pts = AXES.map(a => polar(a.angle, r))
    return pts.map(p => `${p.x},${p.y}`).join(' ')
  })
)

// Axis endpoints
const axisEndpoints = computed(() =>
  AXES.map(a => ({ ...polar(a.angle, R.value), color: a.color, key: a.key }))
)

// Data polygon
const dataPoints = computed(() =>
  AXES.map(a => {
    const pct = Math.min(props.scores[a.key] ?? 0, 100)
    return polar(a.angle, (R.value * pct) / 100)
  })
)
const dataPolygon = computed(() => dataPoints.value.map(p => `${p.x},${p.y}`).join(' '))

// Axis labels (pushed slightly beyond the ring)
const labels = computed(() =>
  AXES.map(a => {
    const p = polar(a.angle, R.value + 18)
    return { ...p, label: a.label, color: a.color, score: props.scores[a.key] ?? 0 }
  })
)
</script>

<template>
  <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" class="overflow-visible">
    <!-- Background rings -->
    <polygon
      v-for="(pts, i) in rings" :key="i"
      :points="pts"
      fill="none"
      stroke="#e5e7eb"
      stroke-width="1"
    />

    <!-- Axis lines -->
    <line
      v-for="ep in axisEndpoints" :key="ep.key"
      :x1="CX" :y1="CY"
      :x2="ep.x" :y2="ep.y"
      stroke="#e5e7eb"
      stroke-width="1"
    />

    <!-- Data polygon -->
    <polygon
      :points="dataPolygon"
      fill="#6366f140"
      stroke="#6366f1"
      stroke-width="2"
      stroke-linejoin="round"
    />

    <!-- Data dots -->
    <circle
      v-for="(pt, i) in dataPoints" :key="AXES[i].key"
      :cx="pt.x" :cy="pt.y" r="4"
      :fill="AXES[i].color"
      stroke="white"
      stroke-width="1.5"
    />

    <!-- Labels -->
    <text
      v-for="l in labels" :key="l.label"
      :x="l.x" :y="l.y"
      text-anchor="middle"
      dominant-baseline="middle"
      font-size="11"
      font-weight="600"
      :fill="l.color"
    >{{ l.label }} {{ l.score }}%</text>
  </svg>
</template>
