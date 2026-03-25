import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import BasicLayout from '../layout/BasicLayout.vue'

const APP_TITLE = '智能定价决策平台'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/index.html',
    redirect: '/'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: BasicLayout,
    redirect: '/import',
    children: [
      {
        path: 'import',
        name: 'DataImport',
        component: () => import('../views/DataImport.vue'),
        meta: { title: '数据管理' }
      },
      {
        path: 'lab',
        name: 'PricingLab',
        component: () => import('../views/PricingLab.vue'),
        meta: { title: '智能定价' }
      },
      {
        path: 'archive',
        name: 'Archive',
        component: () => import('../views/Archive.vue'),
        meta: { title: '决策档案' }
      },
      {
        path: 'profile',
        name: 'PersonalCenter',
        component: () => import('../views/PersonalCenter.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'user',
        name: 'UserManagement',
        component: () => import('../views/UserManagement.vue'),
        meta: { title: '用户管理' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const username = localStorage.getItem('username')

  if (to.path !== '/login' && !username) {
    next('/login')
    return
  }

  if (to.path === '/user' && username !== 'admin') {
    next('/')
    return
  }

  next()
})

router.afterEach((to) => {
  const pageTitle = String(to.meta.title || '首页')
  document.title = `${pageTitle} - ${APP_TITLE}`
})

export default router
