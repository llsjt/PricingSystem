package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductTrendVO;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

public interface ProductService {

    Result<ImportResultVO> importData(MultipartFile file, String dataType);

    Result<Void> addProductManual(ProductManualDTO dto);

    Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource);

    void downloadTemplate(String dataType, HttpServletResponse response);

    Result<Void> batchDelete(List<Long> ids);

    Result<ProductTrendVO> getProductTrend(Long id, int days);

    void generateMockTrendData(Long productId);
}
