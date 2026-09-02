<template>
  <div class="h-screen flex flex-col overflow-hidden">
    <!-- Navbar -->
    <nav class="bg-white border-b border-gray-200 px-6 py-2 flex items-center gap-4 shadow-sm shrink-0">
      <router-link to="/" class="flex items-center gap-2">
        <span class="text-xl">⚗️</span>
        <span class="font-bold text-base text-indigo-700 tracking-tight">FAIR Studio</span>
      </router-link>
      <span class="text-gray-300">|</span>
      <span class="text-xs text-gray-500">AI-Powered FAIR Data Assessment</span>
      <div class="ml-auto flex gap-2 text-xs">
        <span class="px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">F</span>
        <span class="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-medium">A</span>
        <span class="px-2 py-1 rounded-full bg-violet-100 text-violet-700 font-medium">I</span>
        <span class="px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-medium">R</span>
      </div>
    </nav>
    <main class="flex-1 overflow-y-auto bg-gray-50">
      <router-view />
    </main>
  </div>
</template>
