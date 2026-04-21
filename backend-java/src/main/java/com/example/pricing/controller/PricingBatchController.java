package com.example.pricing.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.PricingBatchCreateDTO;
import com.example.pricing.service.PricingBatchService;
import com.example.pricing.vo.PricingBatchCancelVO;
import com.example.pricing.vo.PricingBatchCreateVO;
import com.example.pricing.vo.PricingBatchDetailVO;
import com.example.pricing.vo.PricingBatchItemVO;
import jakarta.validation.Valid;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.validation.annotation.Validated;

/**
 * 批量定价控制器，提供批次创建、列表、详情和取消等接口。
 */
@RestController
@RequestMapping("/api/pricing/batches")
@RequiredArgsConstructor
@Slf4j
@Validated
public class PricingBatchController {

    private final PricingBatchService pricingBatchService;

    @PostMapping
    public Result<PricingBatchCreateVO> createBatch(@Valid @RequestBody PricingBatchCreateDTO request, HttpServletRequest httpRequest) {
        try {
            return Result.success(pricingBatchService.createBatch(request, getCurrentUserId(httpRequest)));
        } catch (Exception e) {
            log.error("create pricing batch failed", e);
            return Result.error(e.getMessage());
        }
    }

    @GetMapping
    public Result<Page<PricingBatchDetailVO>> getRecentBatches(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "5") int size,
            @RequestParam(required = false) String status,
            HttpServletRequest request
    ) {
        try {
            return Result.success(pricingBatchService.getRecentBatches(page, size, status, getCurrentUserId(request)));
        } catch (Exception e) {
            log.error("get recent pricing batches failed", e);
            return Result.error(e.getMessage());
        }
    }

    @GetMapping("/{batchId}")
    public Result<PricingBatchDetailVO> getBatchDetail(@PathVariable Long batchId, HttpServletRequest request) {
        try {
            return Result.success(pricingBatchService.getBatchDetail(batchId, getCurrentUserId(request)));
        } catch (Exception e) {
            log.error("get pricing batch detail failed, batchId={}", batchId, e);
            return Result.error(e.getMessage());
        }
    }

    @GetMapping("/{batchId}/items")
    public Result<Page<PricingBatchItemVO>> getBatchItems(
            @PathVariable Long batchId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String status,
            HttpServletRequest request
    ) {
        try {
            return Result.success(pricingBatchService.getBatchItems(batchId, page, size, status, getCurrentUserId(request)));
        } catch (Exception e) {
            log.error("get pricing batch items failed, batchId={}", batchId, e);
            return Result.error(e.getMessage());
        }
    }

    @PostMapping("/{batchId}/cancel")
    public Result<PricingBatchCancelVO> cancelBatch(@PathVariable Long batchId, HttpServletRequest request) {
        try {
            return Result.success(pricingBatchService.cancelBatch(batchId, getCurrentUserId(request)));
        } catch (Exception e) {
            log.error("cancel pricing batch failed, batchId={}", batchId, e);
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
