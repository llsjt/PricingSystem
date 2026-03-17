import request from './request'

export const login = (data: any) => {
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

export const getUserList = (params: any) => {
  return request({
    url: '/user/list',
    method: 'get',
    params
  })
}

export const addUser = (data: any) => {
  return request({
    url: '/user/add',
    method: 'post',
    data
  })
}

export const updateUser = (id: number, data: any) => {
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
