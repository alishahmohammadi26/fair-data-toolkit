import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

import HomeView   from './views/HomeView.vue'
import RunView    from './views/RunView.vue'
import ResultView from './views/ResultView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',           name: 'home',   component: HomeView   },
    { path: '/run/:id',    name: 'run',    component: RunView    },
    { path: '/result/:id', name: 'result', component: ResultView },
  ],
})

createApp(App).use(router).mount('#app')
