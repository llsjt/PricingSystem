package com.example.pricing.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户列表视图对象。
 */
@Data
public class UserListVO {
    private Long id;
    private String username;
    private String email;
    private Integer status;
    private String role;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
