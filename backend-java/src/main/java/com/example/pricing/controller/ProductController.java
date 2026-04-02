package com.example.pricing.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.service.ProductService;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductDailyMetricVO;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductSkuVO;
import com.example.pricing.vo.ProductTrendVO;
import com.example.pricing.vo.TrafficPromoDailyVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
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
     * 导入商品相关 Excel 数据，支持商品基础信息、SKU 和经营数据。
     */
    @PostMapping("/import")
    public Result<ImportResultVO> importData(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "dataType", required = false) String dataType,
            @RequestParam(value = "platform", required = false) String platform
    ) {
        return productService.importData(file, dataType, platform);
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
     * 手工新增单个商品，并为其补齐基础经营数据。
     */
    @PostMapping("/add")
    public Result<Void> addProductManual(@RequestBody ProductManualDTO dto) {
        return productService.addProductManual(dto);
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
            @RequestParam(required = false) String platform
    ) {
        return productService.getProductList(page, size, keyword, dataSource, platform);
    }

    /**
     * 批量删除商品及其关联的经营、流量和定价记录。
     */
    @DeleteMapping("/batch-delete")
    public Result<Void> batchDelete(@RequestParam("ids") List<Long> ids) {
        return productService.batchDelete(ids);
    }

    /**
     * 查询单个商品的趋势图数据和增长概览。
     */
    @GetMapping("/{id}/trend")
    public Result<ProductTrendVO> getProductTrend(
            @PathVariable Long id,
            @RequestParam(defaultValue = "30") int days
    ) {
        return productService.getProductTrend(id, days);
    }

    /**
     * 查询商品日维度经营指标，供表格或图表展示。
     */
    @GetMapping("/{id}/daily-metrics")
    public Result<List<ProductDailyMetricVO>> getProductDailyMetrics(
            @PathVariable Long id,
            @RequestParam(defaultValue = "90") Integer limit
    ) {
        return productService.getProductDailyMetrics(id, limit);
    }

    /**
     * 查询商品下的 SKU 明细。
     */
    @GetMapping("/{id}/skus")
    public Result<List<ProductSkuVO>> getProductSkus(@PathVariable Long id) {
        return productService.getProductSkus(id);
    }

    /**
     * 查询商品对应的流量推广日报数据。
     */
    @GetMapping("/{id}/traffic-promo")
    public Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(
            @PathVariable Long id,
            @RequestParam(defaultValue = "90") Integer limit
    ) {
        return productService.getTrafficPromoDaily(id, limit);
    }
}
