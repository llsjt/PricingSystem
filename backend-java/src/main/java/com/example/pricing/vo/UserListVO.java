package com.example.pricing.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class UserListVO {
    private Long id;
    private String username;
    private String email;
    private Integer status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
