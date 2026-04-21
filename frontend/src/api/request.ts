/**
 * Axios 请求基座，统一处理鉴权、刷新令牌和错误兜底。
 */

import axios, { type AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { clearAuthSession, getAuthToken, saveAuthSession } from '../utils/authSession'
import { sanitizeErrorMessage } from '../utils/error'

export interface ApiResponse<T = any> {
  code: number
  data: T
  message?: string
  traceId?: string
}

type RequestClient = Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> & {
  <T = any>(config: AxiosRequestConfig): Promise<T>
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
}

type RetriableConfig = AxiosRequestConfig & { __retry?: boolean }

const service = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true
})

let refreshPromise: Promise<string> | null = null

const errorMessageOrFallback = (value: unknown, fallback: string) => sanitizeErrorMessage(value, fallback)

const redirectToLogin = () => {
  clearAuthSession()
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

const refreshAccessToken = async () => {
  if (!refreshPromise) {
    refreshPromise = axios.post<ApiResponse<any>>('/api/user/refresh', {}, { withCredentials: true })
      .then((response) => {
        const payload = response.data
        if (payload.code !== 200 || !payload.data?.token) {
          throw new Error(errorMessageOrFallback(payload.message, 'refresh failed'))
        }
        saveAuthSession({
          token: payload.data.token,
          username: payload.data.username,
          role: payload.data.role,
          isAdmin: Boolean(payload.data.isAdmin)
        })
        return String(payload.data.token)
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

service.interceptors.request.use(
  (config) => {
    const token = getAuthToken()
    if (token) {
      config.headers = {
        ...(config.headers || {}),
        Authorization: `Bearer ${token}`
      } as any
    }
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError<any>) => {
    const originalRequest = (error.config || {}) as RetriableConfig
    const status = error.response?.status
    const requestUrl = String(originalRequest.url || '')

    if (status === 401 && !originalRequest.__retry && !requestUrl.includes('/user/login') && !requestUrl.includes('/user/refresh')) {
      originalRequest.__retry = true
      try {
        const token = await refreshAccessToken()
        originalRequest.headers = {
          ...(originalRequest.headers || {}),
          Authorization: `Bearer ${token}`
        }
        return service(originalRequest)
      } catch {
        ElMessage.error('登录状态无效，请重新登录')
        redirectToLogin()
        return Promise.reject(error)
      }
    }

    if (status === 401) {
      ElMessage.error(errorMessageOrFallback(error.response?.data?.message, '登录状态无效，请重新登录'))
      redirectToLogin()
      return Promise.reject(error)
    }

    if (status === 403) {
      ElMessage.error(errorMessageOrFallback(error.response?.data?.message, '没有权限访问该资源'))
      return Promise.reject(error)
    }

    if (status === 500) {
      ElMessage.error(errorMessageOrFallback(error.response?.data?.message, '服务器内部错误'))
      return Promise.reject(error)
    }

    if (error.response) {
      ElMessage.error(errorMessageOrFallback(error.response.data?.message, '请求失败'))
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default service as RequestClient
