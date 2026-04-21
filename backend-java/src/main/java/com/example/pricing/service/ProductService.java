/*
 * 商品服务接口，定义商品查询、导入和维护相关业务能力。
 */

package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductDailyMetricPageVO;
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
     * 导入商品相关数据（指定目标店铺）。
     */
    Result<ImportResultVO> importData(MultipartFile file, String dataType, String platform, Long shopId, Long userId);

    /**
     * 手工新增商品。
     */
    Result<Void> addProductManual(ProductManualDTO dto, Long userId);

    /**
     * 分页查询商品列表（按用户过滤）。
     */
    Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource, String platform, String status, Long shopId, Long userId);

    /**
     * 下载导入模板。
     */
    void downloadTemplate(String dataType, HttpServletResponse response);

    /**
     * 批量删除商品（校验归属）。
     */
    Result<Void> batchDelete(List<Long> ids, Long userId);

    /**
     * 获取商品趋势分析数据（校验归属）。
     */
    Result<ProductTrendVO> getProductTrend(Long id, int days, Long userId);

    /**
     * 获取商品日经营指标（校验归属）。
     */
    Result<ProductDailyMetricPageVO> getProductDailyMetrics(Long productId, Integer page, Integer size, Long userId);

    /**
     * 获取商品 SKU 列表（校验归属）。
     */
    Result<List<ProductSkuVO>> getProductSkus(Long productId, Long userId);

    /**
     * 获取商品流量推广日报（校验归属）。
     */
    Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(Long productId, Integer limit, Long userId);
}
