<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: Number, default: 0 },
  label: { type: String, default: '' },
  color: { type: String, default: '#6366f1' },
  size:  { type: Number, default: 110 },
})

const radius        = 38
const circumference = 2 * Math.PI * radius
const offset        = computed(() => circumference - (Math.min(props.score, 100) / 100) * circumference)
const cx            = computed(() => props.size / 2)
const strokeWidth   = computed(() => props.size < 120 ? 8 : 10)
</script>

<template>
  <div class="flex flex-col items-center gap-1">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <circle :cx="cx" :cy="cx" :r="radius" fill="none" stroke="#f3f4f6" :stroke-width="strokeWidth" />
      <circle
        :cx="cx" :cy="cx" :r="radius"
        fill="none"
        :stroke="color"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
        :transform="`rotate(-90 ${cx} ${cx})`"
        style="transition: stroke-dashoffset 0.6s ease"
      />
      <text :x="cx" :y="cx + 6" text-anchor="middle" :fill="color" font-weight="bold"
        :font-size="size < 120 ? 16 : 20">
        {{ score }}%
      </text>
    </svg>
    <span class="text-xs font-medium text-gray-500">{{ label }}</span>
  </div>
</template>
