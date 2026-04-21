/**
 * 店铺管理接口封装，负责店铺列表、新增、修改和删除请求。
 */

import request from './request'

export interface Shop {
  id: number
  userId: number
  shopName: string
  platform: string
  sellerNick: string
  createdAt: string
  updatedAt: string
}

export interface ShopCreateDTO {
  shopName: string
  platform: string
  sellerNick?: string
}

export interface ShopUpdateDTO {
  shopName: string
  platform: string
  sellerNick?: string
}

export const getShopList = () => request.get<any>('/shops')
export const createShop = (data: ShopCreateDTO) => request.post<any>('/shops', data)
export const updateShop = (id: number, data: ShopUpdateDTO) => request.put<any>(`/shops/${id}`, data)
export const deleteShop = (id: number) => request.delete<any>(`/shops/${id}`)
