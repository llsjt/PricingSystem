package com.example.pricing.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.MockExcelExportDTO;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.service.ProductService;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductDailyMetricPageVO;
import com.example.pricing.vo.ProductDailyMetricVO;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductSkuVO;
import com.example.pricing.vo.ProductTrendVO;
import com.example.pricing.vo.TrafficPromoDailyVO;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 商品管理控制器，负责导入、手工新增、列表查询和商品趋势查看等接口。
 */
@RestController
@RequestMapping("/api/products")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ProductController {

    private final ProductService productService;

    /**
     * 导入商品相关 Excel 数据，需指定目标店铺。
     */
    @PostMapping("/import")
    public Result<ImportResultVO> importData(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "dataType", required = false) String dataType,
            @RequestParam(value = "platform", required = false) String platform,
            @RequestParam("shopId") Long shopId,
            HttpServletRequest request
    ) {
        return productService.importData(file, dataType, platform, shopId, getCurrentUserId(request));
    }

    /**
     * 下载指定数据类型的导入模板，方便按标准格式整理 Excel。
     */
    @GetMapping("/template")
    public void downloadTemplate(
            @RequestParam(value = "dataType", required = false) String dataType,
            HttpServletResponse response
    ) {
        productService.downloadTemplate(dataType, response);
    }

    /**
     * 下载模拟电商平台导出数据，压缩包内包含 4 个可直接导入系统的 Excel。
     */
    @PostMapping("/mock-export")
    public void downloadMockExport(
            @RequestBody(required = false) MockExcelExportDTO dto,
            HttpServletResponse response
    ) {
        productService.downloadMockExcelBundle(dto, response);
    }

    /**
     * 手工新增单个商品，并为其补齐基础经营数据。
     */
    @PostMapping("/add")
    public Result<Void> addProductManual(@RequestBody ProductManualDTO dto, HttpServletRequest request) {
        return productService.addProductManual(dto, getCurrentUserId(request));
    }

    /**
     * 分页查询商品列表，可按关键字和平台筛选。
     */
    @GetMapping("/list")
    public Result<Page<ProductListVO>> getProductList(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String dataSource,
            @RequestParam(required = false) String platform,
            HttpServletRequest request
    ) {
        return productService.getProductList(page, size, keyword, dataSource, platform, getCurrentUserId(request));
    }

    /**
     * 批量删除商品及其关联的经营、流量和定价记录。
     */
    @DeleteMapping("/batch-delete")
    public Result<Void> batchDelete(@RequestParam("ids") List<Long> ids, HttpServletRequest request) {
        return productService.batchDelete(ids, getCurrentUserId(request));
    }

    /**
     * 查询单个商品的趋势图数据和增长概览。
     */
    @GetMapping("/{id}/trend")
    public Result<ProductTrendVO> getProductTrend(
            @PathVariable Long id,
            @RequestParam(defaultValue = "30") int days,
            HttpServletRequest request
    ) {
        return productService.getProductTrend(id, days, getCurrentUserId(request));
    }

    /**
     * 查询商品日维度经营指标，供表格或图表展示。
     */
    @GetMapping("/{id}/daily-metrics")
    public Result<ProductDailyMetricPageVO> getProductDailyMetrics(
            @PathVariable Long id,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer size,
            HttpServletRequest request
    ) {
        return productService.getProductDailyMetrics(id, page, size, getCurrentUserId(request));
    }

    /**
     * 查询商品下的 SKU 明细。
     */
    @GetMapping("/{id}/skus")
    public Result<List<ProductSkuVO>> getProductSkus(@PathVariable Long id, HttpServletRequest request) {
        return productService.getProductSkus(id, getCurrentUserId(request));
    }

    /**
     * 查询商品对应的流量推广日报数据。
     */
    @GetMapping("/{id}/traffic-promo")
    public Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(
            @PathVariable Long id,
            @RequestParam(defaultValue = "90") Integer limit,
            HttpServletRequest request
    ) {
        return productService.getTrafficPromoDaily(id, limit, getCurrentUserId(request));
    }

    private Long getCurrentUserId(HttpServletRequest request) {
        Long userId = (Long) request.getAttribute("currentUserId");
        if (userId == null) {
            throw new IllegalStateException("请先登录");
        }
        return userId;
    }
}
