package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.dto.PricingBatchCreateDTO;
import com.example.pricing.vo.PricingBatchCancelVO;
import com.example.pricing.vo.PricingBatchCreateVO;
import com.example.pricing.vo.PricingBatchDetailVO;
import com.example.pricing.vo.PricingBatchItemVO;

/**
 * 批量定价服务接口，定义批次创建、查询和取消的业务能力。
 */
public interface PricingBatchService {

    PricingBatchCreateVO createBatch(PricingBatchCreateDTO request, Long userId);

    Page<PricingBatchDetailVO> getRecentBatches(int page, int size, String status, Long userId);

    PricingBatchDetailVO getBatchDetail(Long batchId, Long userId);

    Page<PricingBatchItemVO> getBatchItems(Long batchId, int page, int size, String status, Long userId);

    PricingBatchCancelVO cancelBatch(Long batchId, Long userId);
}
