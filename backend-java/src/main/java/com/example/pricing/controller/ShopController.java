/*
 * 店铺控制器，负责店铺列表、新增、修改和删除接口。
 */

package com.example.pricing.controller;

import com.example.pricing.common.Result;
import com.example.pricing.dto.ShopCreateDTO;
import com.example.pricing.dto.ShopUpdateDTO;
import com.example.pricing.entity.Shop;
import com.example.pricing.service.ShopService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 店铺管理控制器，提供当前用户的店铺 CRUD 能力。
 */
@RestController
@RequestMapping("/api/shops")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ShopController {

    private final ShopService shopService;

    @GetMapping
    public Result<List<Shop>> list(HttpServletRequest request) {
        return Result.success(shopService.listByUser(getCurrentUserId(request)));
    }

    @PostMapping
    public Result<Shop> create(@RequestBody ShopCreateDTO dto, HttpServletRequest request) {
        try {
            return Result.success(shopService.create(getCurrentUserId(request), dto));
        } catch (IllegalArgumentException e) {
            return Result.error(e.getMessage());
        }
    }

    @PutMapping("/{id}")
    public Result<Shop> update(@PathVariable Long id, @RequestBody ShopUpdateDTO dto, HttpServletRequest request) {
        try {
            return Result.success(shopService.update(id, getCurrentUserId(request), dto));
        } catch (IllegalArgumentException e) {
            return Result.error(e.getMessage());
        }
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id, HttpServletRequest request) {
        try {
            shopService.delete(id, getCurrentUserId(request));
            return Result.success();
        } catch (IllegalArgumentException e) {
            return Result.error(e.getMessage());
        }
    }

    private Long getCurrentUserId(HttpServletRequest request) {
        Long userId = (Long) request.getAttribute("currentUserId");
        if (userId == null) {
            throw new IllegalStateException("请先登录");
        }
        return userId;
    }
}
