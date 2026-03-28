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

@RestController
@RequestMapping("/api/products")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ProductController {

    private final ProductService productService;

    @PostMapping("/import")
    public Result<ImportResultVO> importData(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "dataType", required = false) String dataType,
            @RequestParam(value = "platform", required = false) String platform
    ) {
        return productService.importData(file, dataType, platform);
    }

    @GetMapping("/template")
    public void downloadTemplate(
            @RequestParam(value = "dataType", required = false) String dataType,
            HttpServletResponse response
    ) {
        productService.downloadTemplate(dataType, response);
    }

    @PostMapping("/add")
    public Result<Void> addProductManual(@RequestBody ProductManualDTO dto) {
        return productService.addProductManual(dto);
    }

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

    @DeleteMapping("/batch-delete")
    public Result<Void> batchDelete(@RequestParam("ids") List<Long> ids) {
        return productService.batchDelete(ids);
    }

    @GetMapping("/{id}/trend")
    public Result<ProductTrendVO> getProductTrend(
            @PathVariable Long id,
            @RequestParam(defaultValue = "30") int days
    ) {
        return productService.getProductTrend(id, days);
    }

    @GetMapping("/{id}/daily-metrics")
    public Result<List<ProductDailyMetricVO>> getProductDailyMetrics(
            @PathVariable Long id,
            @RequestParam(defaultValue = "90") Integer limit
    ) {
        return productService.getProductDailyMetrics(id, limit);
    }

    @GetMapping("/{id}/skus")
    public Result<List<ProductSkuVO>> getProductSkus(@PathVariable Long id) {
        return productService.getProductSkus(id);
    }

    @GetMapping("/{id}/traffic-promo")
    public Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(
            @PathVariable Long id,
            @RequestParam(defaultValue = "90") Integer limit
    ) {
        return productService.getTrafficPromoDaily(id, limit);
    }
}
