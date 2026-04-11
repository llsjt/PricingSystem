import { Connection, DataLine, Document, Files, Shop, User, UserFilled } from '@element-plus/icons-vue'
import type { Component } from 'vue'

export interface AppNavItem {
  path: string
  title: string
  desc: string
  icon: Component
  adminOnly?: boolean
}

export const APP_NAME = '智能定价平台'
export const APP_SUBTITLE = 'Excel 导入与定价协作'
export const APP_TITLE = '智能定价决策平台'

export const APP_NAV_ITEMS: AppNavItem[] = [
  {
    path: '/import',
    title: '数据管理',
    desc: '商品管理与批量导入',
    icon: Document
  },
  {
    path: '/lab',
    title: '智能定价',
    desc: '任务配置与结果分析',
    icon: DataLine
  },
  {
    path: '/archive',
    title: '决策档案',
    desc: '任务记录与复盘报表',
    icon: Files
  },
  {
    path: '/shops',
    title: '店铺管理',
    desc: '管理电商平台店铺信息',
    icon: Shop
  },
  {
    path: '/profile',
    title: '个人中心',
    desc: '查看个人信息与账户状态',
    icon: UserFilled
  },
  {
    path: '/models',
    title: '模型管理',
    desc: '管理个人模型 API 配置',
    icon: Connection
  },
  {
    path: '/user',
    title: '用户管理',
    desc: '账号维护与权限管理',
    icon: User,
    adminOnly: true
  }
]

export const findNavItemByPath = (path: string, items: AppNavItem[] = APP_NAV_ITEMS) =>
  items.find((item) => path.startsWith(item.path))

export const getNavTitleByPath = (path: string, fallback = '首页') =>
  findNavItemByPath(path)?.title || fallback
