package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductImportDTO;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.vo.ProductListVO;
import org.springframework.web.multipart.MultipartFile;
import jakarta.servlet.http.HttpServletResponse;
import java.util.List;

public interface ProductService {
    /**
     * 导入Excel数据
     */
    Result<String> importData(MultipartFile file);

    /**
     * 保存单行导入数据 (事务方法)
     */
    void saveImportedProduct(ProductImportDTO dto, Long batchId);

    /**
     * 手动新增商品
     */
    Result<Void> addProductManual(ProductManualDTO dto);

    /**
     * 分页查询商品列表
     */
    Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource);

    /**
     * 下载 Excel 导入模板
     */
    void downloadTemplate(HttpServletResponse response);

    /**
     * 批量删除商品
     */
    Result<Void> batchDelete(List<Long> ids);

    /**
     * 获取商品趋势数据
     */
    Result<com.example.pricing.vo.ProductTrendVO> getProductTrend(Long id, int days);

    /**
     * 生成模拟趋势数据 (用于演示)
     */
    void generateMockTrendData(Long productId);
}
