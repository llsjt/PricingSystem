/*
 * 店铺新增请求对象。
 */

package com.example.pricing.dto;

import lombok.Data;

/**
 * 新建店铺请求体。
 */
@Data
public class ShopCreateDTO {
    private String shopName;
    private String platform;
    private String sellerNick;
}
