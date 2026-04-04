package com.example.pricing.dto;

import lombok.Data;

/**
 * 更新店铺请求体。
 */
@Data
public class ShopUpdateDTO {
    private String shopName;
    private String platform;
    private String sellerNick;
}
