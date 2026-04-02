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

/**
 * 商品服务接口，定义导入、查询、删除和趋势分析等商品管理能力。
 */
public interface ProductService {

    /**
     * 导入商品相关数据。
     */
    Result<ImportResultVO> importData(MultipartFile file, String dataType, String platform);

    /**
     * 手工新增商品。
     */
    Result<Void> addProductManual(ProductManualDTO dto);

    /**
     * 分页查询商品列表。
     */
    Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource, String platform);

    /**
     * 下载导入模板。
     */
    void downloadTemplate(String dataType, HttpServletResponse response);

    /**
     * 批量删除商品。
     */
    Result<Void> batchDelete(List<Long> ids);

    /**
     * 获取商品趋势分析数据。
     */
    Result<ProductTrendVO> getProductTrend(Long id, int days);

    /**
     * 获取商品日经营指标。
     */
    Result<List<ProductDailyMetricVO>> getProductDailyMetrics(Long productId, Integer limit);

    /**
     * 获取商品 SKU 列表。
     */
    Result<List<ProductSkuVO>> getProductSkus(Long productId);

    /**
     * 获取商品流量推广日报。
     */
    Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(Long productId, Integer limit);


}
