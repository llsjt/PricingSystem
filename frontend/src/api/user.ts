import request from './request'

export interface LoginPayload {
  username: string
  password: string
}

export interface UserListItem {
  id: number
  username: string
  email: string
  status: number
  createdAt: string
  updatedAt: string
}

export interface UserPayload {
  username: string
  password?: string
  email: string
  status?: number
}

export const login = (data: LoginPayload) => {
  return request({
    url: '/user/login',
    method: 'post',
    data
  })
}

export const logout = () => {
  return request({
    url: '/user/logout',
    method: 'post'
  })
}

export const getUserList = (params: { page: number; size: number }) => {
  return request({
    url: '/user/list',
    method: 'get',
    params
  })
}

export const addUser = (data: UserPayload) => {
  return request({
    url: '/user/add',
    method: 'post',
    data
  })
}

export const updateUser = (id: number, data: UserPayload) => {
  return request({
    url: `/user/${id}`,
    method: 'put',
    data
  })
}

export const deleteUser = (id: number) => {
  return request({
    url: `/user/${id}`,
    method: 'delete'
  })
}

export const batchDeleteUsers = (ids: number[]) => {
  return request.delete('/user/batch-delete', {
    params: { ids: ids.join(',') }
  })
}
