package com.example.pricing.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductImportDTO;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.service.ProductService;
import com.example.pricing.vo.ProductListVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import jakarta.servlet.http.HttpServletResponse;
import java.util.List;

/**
 * 商品管理控制器
 */
@RestController
@RequestMapping("/api/products")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ProductController {

    private final ProductService productService;

    /**
     * 导入商品数据 (Excel)
     */
    @PostMapping("/import")
    public Result<String> importData(@RequestParam("file") MultipartFile file) {
        return productService.importData(file);
    }

    /**
     * 下载导入模板
     */
    @GetMapping("/template")
    public void downloadTemplate(HttpServletResponse response) {
        productService.downloadTemplate(response);
    }

    /**
     * 手动新增商品
     */
    @PostMapping("/add")
    public Result<Void> addProductManual(@RequestBody ProductManualDTO dto) {
        return productService.addProductManual(dto);
    }

    /**
     * 分页查询商品列表
     */
    @GetMapping("/list")
    public Result<Page<ProductListVO>> getProductList(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String dataSource
    ) {
        return productService.getProductList(page, size, keyword, dataSource);
    }

    /**
     * 批量删除商品
     */
    @DeleteMapping("/batch-delete")
    public Result<Void> batchDelete(@RequestParam("ids") List<Long> ids) {
        return productService.batchDelete(ids);
    }

    /**
     * 获取商品经营趋势数据
     */
    @GetMapping("/{id}/trend")
    public Result<com.example.pricing.vo.ProductTrendVO> getProductTrend(
            @PathVariable Long id,
            @RequestParam(defaultValue = "30") int days) {
        return productService.getProductTrend(id, days);
    }
}
