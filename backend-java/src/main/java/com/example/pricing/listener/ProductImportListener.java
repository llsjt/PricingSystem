package com.example.pricing.listener;

import com.alibaba.excel.context.AnalysisContext;
import com.alibaba.excel.event.AnalysisEventListener;
import com.example.pricing.dto.ProductImportDTO;
import com.example.pricing.service.ProductService;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.util.ArrayList;
import java.util.List;

/**
 * Excel导入监听器
 * 负责逐行读取Excel数据并调用Service进行保存
 */
@Slf4j
public class ProductImportListener extends AnalysisEventListener<ProductImportDTO> {

    private final ProductService productService;
    private final Long batchId;

    @Getter
    private int successCount = 0;
    @Getter
    private int failCount = 0;
    @Getter
    private final List<String> errorMessages = new ArrayList<>();

    public ProductImportListener(ProductService productService, Long batchId) {
        this.productService = productService;
        this.batchId = batchId;
    }

    @Override
    public void invoke(ProductImportDTO data, AnalysisContext context) {
        log.info("第{}行读取到数据：{}", context.readRowHolder().getRowIndex() + 1, data.getTitle());
        try {
            log.info("开始验证第{}行数据", context.readRowHolder().getRowIndex() + 1);
            validateData(data);
            log.info("第{}行验证通过，开始保存", context.readRowHolder().getRowIndex() + 1);
            productService.saveImportedProduct(data, batchId);
            successCount++;
            log.info("第{}行导入成功：{}", context.readRowHolder().getRowIndex() + 1, data.getTitle());
        } catch (Exception e) {
            failCount++;
            String errorMsg = String.format("第%d行解析失败：%s", context.readRowHolder().getRowIndex() + 1, e.getMessage());
            errorMessages.add(errorMsg);
            log.error("Import error: {}", errorMsg, e);
        }
    }

    private void validateData(ProductImportDTO data) {
        // 只校验商品标题，其他字段允许为空，在 Service 层设置默认值
        if (data.getTitle() == null || data.getTitle().trim().isEmpty()) {
            throw new IllegalArgumentException("商品标题不能为空");
        }
    }

    @Override
    public void doAfterAllAnalysed(AnalysisContext context) {
        log.info("所有数据解析完成！成功: {}, 失败: {}", successCount, failCount);
    }
}
