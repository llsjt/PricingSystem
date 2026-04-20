package com.example.pricing.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.ProductDailyMetric;
import com.example.pricing.entity.Shop;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ProductSkuMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import com.example.pricing.service.ShopService;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductTrendVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProductServiceImplTest {

    @Mock
    private ProductMapper productMapper;

    @Mock
    private ProductDailyMetricMapper statMapper;

    @Mock
    private ProductSkuMapper productSkuMapper;

    @Mock
    private TrafficPromoDailyMapper trafficPromoDailyMapper;

    @Mock
    private PricingTaskMapper pricingTaskMapper;

    @Mock
    private PricingResultMapper pricingResultMapper;

    @Mock
    private AgentRunLogMapper agentRunLogMapper;

    @Mock
    private ShopMapper shopMapper;

    @Mock
    private ShopService shopService;

    @Mock
    private TaobaoExcelImportService taobaoExcelImportService;

    private ProductServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new ProductServiceImpl(
                productMapper,
                statMapper,
                productSkuMapper,
                trafficPromoDailyMapper,
                pricingTaskMapper,
                pricingResultMapper,
                agentRunLogMapper,
                shopMapper,
                shopService,
                taobaoExcelImportService
        );
    }

    @Test
    void productListSummaryUsesLatestImportedMetricWindow() {
        Product product = product(101L, 9L, "tmall-101");
        ProductDailyMetric older = metric(product.getId(), LocalDate.of(2025, 10, 18), 100, 10);
        ProductDailyMetric latest = metric(product.getId(), LocalDate.of(2025, 10, 19), 1000, 10);
        AtomicBoolean latestDateResolved = new AtomicBoolean(false);

        when(shopService.getShopIdsByUser(7L)).thenReturn(List.of(9L));
        when(productMapper.selectPage(any(), any())).thenReturn(productPage(product));
        when(shopMapper.selectList(any())).thenReturn(List.of(shop(9L)));
        when(statMapper.selectOne(any())).thenAnswer(invocation -> {
            latestDateResolved.set(true);
            return latest;
        });
        when(statMapper.selectList(any())).thenAnswer(invocation ->
                latestDateResolved.get() ? List.of(older, latest) : List.of()
        );

        Result<Page<ProductListVO>> result = service.getProductList(1, 10, null, null, null, null, null, 7L);

        ProductListVO row = result.getData().getRecords().get(0);
        assertEquals(20, row.getMonthlySales());
        assertEquals(new BigDecimal("0.0182"), row.getConversionRate());
    }

    @Test
    void productTrendUsesLatestImportedMetricWindow() {
        Product product = product(101L, 9L, "tmall-101");
        ProductDailyMetric older = metric(product.getId(), LocalDate.of(2025, 10, 18), 100, 10);
        ProductDailyMetric latest = metric(product.getId(), LocalDate.of(2025, 10, 19), 1000, 10);
        AtomicBoolean latestDateResolved = new AtomicBoolean(false);

        when(productMapper.selectById(101L)).thenReturn(product);
        when(shopService.getShopIdsByUser(7L)).thenReturn(List.of(9L));
        when(statMapper.selectOne(any())).thenAnswer(invocation -> {
            if (!latestDateResolved.get()) {
                latestDateResolved.set(true);
                return latest;
            }
            return older;
        });
        when(statMapper.selectList(any())).thenAnswer(invocation ->
                latestDateResolved.get() ? List.of(older, latest) : List.of()
        );

        Result<ProductTrendVO> result = service.getProductTrend(101L, 2, 7L);

        ProductTrendVO trend = result.getData();
        assertEquals(List.of("2025-10-18", "2025-10-19"), trend.getDates());
        assertEquals(List.of(100, 1000), trend.getVisitors());
        assertEquals(List.of(10, 10), trend.getSales());
    }

    private Page<Product> productPage(Product product) {
        Page<Product> page = new Page<>(1, 10);
        page.setTotal(1);
        page.setRecords(List.of(product));
        return page;
    }

    private Product product(Long id, Long shopId, String externalProductId) {
        Product product = new Product();
        product.setId(id);
        product.setShopId(shopId);
        product.setExternalProductId(externalProductId);
        product.setTitle("商品");
        product.setCurrentPrice(new BigDecimal("19.90"));
        product.setCostPrice(new BigDecimal("9.90"));
        product.setStock(88);
        product.setStatus("出售中");
        return product;
    }

    private ProductDailyMetric metric(Long productId, LocalDate statDate, int visitors, int sales) {
        ProductDailyMetric metric = new ProductDailyMetric();
        metric.setProductId(productId);
        metric.setStatDate(statDate);
        metric.setVisitorCount(visitors);
        metric.setSalesCount(sales);
        metric.setTurnover(new BigDecimal("199.00"));
        metric.setRefundAmount(BigDecimal.ZERO);
        metric.setConversionRate(null);
        return metric;
    }

    private Shop shop(Long id) {
        Shop shop = new Shop();
        shop.setId(id);
        shop.setPlatform("天猫");
        return shop;
    }
}
