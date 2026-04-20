import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import BasicLayout from '../layout/BasicLayout.vue'
import { APP_TITLE, getNavTitleByPath } from '../config/navigation'
import { readAuthSession } from '../utils/authSession'

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
        meta: { title: getNavTitleByPath('/import') }
      },
      {
        path: 'lab',
        name: 'PricingLab',
        component: () => import('../views/PricingLab.vue'),
        meta: { title: getNavTitleByPath('/lab') }
      },
      {
        path: 'archive',
        name: 'Archive',
        component: () => import('../views/Archive.vue'),
        meta: { title: getNavTitleByPath('/archive') }
      },
      {
        path: 'archive/batches/:batchId',
        name: 'PricingBatchDetail',
        component: () => import('../views/PricingBatchDetail.vue'),
        meta: { title: '批量定价进度' }
      },
      {
        path: 'shops',
        name: 'ShopManagement',
        component: () => import('../views/ShopManagement.vue'),
        meta: { title: getNavTitleByPath('/shops') }
      },
      {
        path: 'profile',
        name: 'PersonalCenter',
        component: () => import('../views/PersonalCenter.vue'),
        meta: { title: getNavTitleByPath('/profile') }
      },
      {
        path: 'models',
        name: 'ModelManagement',
        component: () => import('../views/ModelManagement.vue'),
        meta: { title: getNavTitleByPath('/models') }
      },
      {
        path: 'user',
        name: 'UserManagement',
        component: () => import('../views/UserManagement.vue'),
        meta: { title: getNavTitleByPath('/user') }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const session = readAuthSession()

  if (to.path !== '/login' && !session.token) {
    next('/login')
    return
  }

  if (to.path === '/user' && !session.isAdmin) {
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
