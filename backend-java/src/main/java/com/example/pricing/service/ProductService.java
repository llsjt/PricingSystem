package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductDailyMetricVO;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductSkuVO;
import com.example.pricing.vo.ProductTrendVO;
import com.example.pricing.vo.TrafficPromoDailyVO;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

public interface ProductService {

    Result<ImportResultVO> importData(MultipartFile file, String dataType, String platform);

    Result<Void> addProductManual(ProductManualDTO dto);

    Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource, String platform);

    void downloadTemplate(String dataType, HttpServletResponse response);

    Result<Void> batchDelete(List<Long> ids);

    Result<ProductTrendVO> getProductTrend(Long id, int days);

    Result<List<ProductDailyMetricVO>> getProductDailyMetrics(Long productId, Integer limit);

    Result<List<ProductSkuVO>> getProductSkus(Long productId);

    Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(Long productId, Integer limit);

    void generateMockTrendData(Long productId);
}
