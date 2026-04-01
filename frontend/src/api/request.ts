import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiResponse<T = any> {
  code: number
  data: T
  message?: string
}

type RequestClient = Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> & {
  <T = any>(config: AxiosRequestConfig): Promise<T>
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
}

const service = axios.create({
  baseURL: '/api',
  timeout: 10000
})

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers = {
        ...(config.headers || {}),
        'Authorization': `Bearer ${token}`
      } as any
    }
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          ElMessage.error('登录状态无效，请重新登录')
          localStorage.removeItem('token')
          localStorage.removeItem('username')
          localStorage.removeItem('isAdmin')
          window.location.href = '/login'
          break
        case 403:
          ElMessage.error('没有权限访问该资源')
          break
        case 500:
          ElMessage.error(error.response.data?.message || '服务器内部错误')
          break
        default:
          ElMessage.error(error.response.data?.message || '请求失败')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default service as RequestClient
