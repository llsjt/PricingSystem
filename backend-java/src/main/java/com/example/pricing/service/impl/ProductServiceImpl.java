package com.example.pricing.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.MockExcelExportDTO;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.ProductDailyMetric;
import com.example.pricing.entity.ProductSku;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.TrafficPromoDaily;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ProductSkuMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import com.example.pricing.service.ProductService;
import com.example.pricing.service.ShopService;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductDailyMetricPageVO;
import com.example.pricing.vo.ProductDailyMetricVO;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductSkuVO;
import com.example.pricing.vo.ProductTrendVO;
import com.example.pricing.vo.TrafficPromoDailyVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 商品服务实现，负责商品导入、手工维护、趋势分析以及相关明细查询。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final ProductMapper productMapper;
    private final ProductDailyMetricMapper statMapper;
    private final ProductSkuMapper productSkuMapper;
    private final TrafficPromoDailyMapper trafficPromoDailyMapper;
    private final PricingTaskMapper pricingTaskMapper;
    private final PricingResultMapper pricingResultMapper;
    private final AgentRunLogMapper agentRunLogMapper;
    private final ShopMapper shopMapper;
    private final ShopService shopService;
    private final TaobaoExcelImportService taobaoExcelImportService;
    private final MockExcelExportService mockExcelExportService;

    // ===== 数据隔离辅助方法 =====

    private List<Long> getUserShopIds(Long userId) {
        return shopService.getShopIdsByUser(userId);
    }

    private void verifyProductOwnership(Product product, Long userId) {
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }
        List<Long> shopIds = getUserShopIds(userId);
        if (!shopIds.contains(product.getShopId())) {
            throw new IllegalArgumentException("无权访问此商品");
        }
    }

    private Long resolveDefaultShopId(Long userId) {
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Shop::getUserId, userId).orderByAsc(Shop::getId).last("LIMIT 1");
        Shop shop = shopMapper.selectOne(wrapper);
        if (shop == null) {
            throw new IllegalStateException("请先创建店铺");
        }
        return shop.getId();
    }

    // ===== 业务方法 =====

    @Override
    public Result<ImportResultVO> importData(MultipartFile file, String dataType, String platform, Long shopId, Long userId) {
        try {
            if (shopId == null) {
                return Result.error("请选择目标店铺");
            }
            // 校验店铺归属
            List<Long> userShopIds = getUserShopIds(userId);
            if (!userShopIds.contains(shopId)) {
                return Result.error("无权操作此店铺");
            }
            return Result.success(taobaoExcelImportService.importExcel(file, dataType, platform, shopId));
        } catch (Exception e) {
            log.error("Import excel failed", e);
            return Result.error(e.getMessage());
        }
    }

    @Override
    public void downloadMockExcelBundle(MockExcelExportDTO dto, HttpServletResponse response) {
        mockExcelExportService.downloadBundle(dto, response);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<Void> addProductManual(ProductManualDTO dto, Long userId) {
        Long shopId = resolveDefaultShopId(userId);
        if (dto.getProductName() == null || dto.getProductName().isBlank()) {
            return Result.error("商品名称不能为空");
        }

        if (findProductByTitle(shopId, dto.getProductName()) != null) {
            return Result.error("商品名称已存在");
        }

        Product product = new Product();
        product.setShopId(shopId);
        product.setExternalProductId(resolveExternalProductId(dto.getExternalProductId()));
        product.setTitle(dto.getProductName().trim());
        product.setCategory(trimToNull(dto.getCategoryName()));
        product.setCostPrice(defaultDecimal(dto.getCostPrice()));
        product.setCurrentPrice(defaultDecimal(dto.getSalePrice()));
        product.setStock(defaultInteger(dto.getStock()));
        product.setStatus(dto.getStatus() == null || dto.getStatus().isBlank() ? "ON_SALE" : dto.getStatus().trim());
        product.setProfileStatus("COMPLETE");
        productMapper.insert(product);

        return Result.success();
    }

    @Override
    public Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource, String platform, Long userId) {
        int safePage = Math.max(page, 1);
        int safeSize = size <= 0 || size > 100 ? 10 : size;

        // 获取当前用户的店铺列表
        List<Long> userShopIds = getUserShopIds(userId);
        if (userShopIds.isEmpty()) {
            return Result.success(emptyPage(safePage, safeSize));
        }

        Page<Product> pageParam = new Page<>(safePage, safeSize);
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();

        // 按用户店铺过滤
        wrapper.in(Product::getShopId, userShopIds);

        if (keyword != null && !keyword.isBlank()) {
            String trimmedKeyword = keyword.trim();
            Long numericKeyword = parseLongOrNull(trimmedKeyword);
            wrapper.and(query -> query.like(Product::getTitle, trimmedKeyword)
                    .or()
                    .like(Product::getCategory, trimmedKeyword)
                    .or()
                    .like(Product::getExternalProductId, trimmedKeyword)
                    .or(numericKeyword != null)
                    .eq(numericKeyword != null, Product::getId, numericKeyword));
        }
        if (platform != null && !platform.isBlank()) {
            LambdaQueryWrapper<Shop> shopWrapper = new LambdaQueryWrapper<>();
            shopWrapper.eq(Shop::getPlatform, platform.trim()).eq(Shop::getUserId, userId);
            List<Long> platformShopIds = shopMapper.selectList(shopWrapper).stream().map(Shop::getId).toList();
            if (platformShopIds.isEmpty()) {
                return Result.success(emptyPage(safePage, safeSize));
            }
            wrapper.in(Product::getShopId, platformShopIds);
        }
        wrapper.orderByDesc(Product::getUpdatedAt, Product::getId);

        Page<Product> productPage = productMapper.selectPage(pageParam, wrapper);
        Map<Long, String> shopPlatformMap = loadShopPlatformMap(productPage.getRecords());
        List<ProductListVO> records = productPage.getRecords().stream().map(product -> {
            ProductMetricSummary summary = loadMetricSummary(product.getId());
            ProductListVO vo = new ProductListVO();
            vo.setId(product.getId());
            vo.setPlatform(shopPlatformMap.getOrDefault(product.getShopId(), "-"));
            vo.setExternalProductId(product.getExternalProductId());
            vo.setProductName(product.getTitle());
            vo.setCategoryName(product.getCategory());
            vo.setCostPrice(product.getCostPrice());
            vo.setSalePrice(product.getCurrentPrice());
            vo.setStock(product.getStock());
            vo.setStatus(product.getStatus());
            vo.setMonthlySales(summary.monthlySales());
            vo.setConversionRate(summary.conversionRate());
            vo.setUpdatedAt(product.getUpdatedAt());
            return vo;
        }).collect(Collectors.toList());

        Page<ProductListVO> resultPage = new Page<>();
        resultPage.setCurrent(productPage.getCurrent());
        resultPage.setSize(productPage.getSize());
        resultPage.setTotal(productPage.getTotal());
        resultPage.setRecords(records);
        return Result.success(resultPage);
    }

    @Override
    public void downloadTemplate(String dataType, HttpServletResponse response) {
        taobaoExcelImportService.downloadTemplate(dataType, response);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<Void> batchDelete(List<Long> ids, Long userId) {
        if (ids == null || ids.isEmpty()) {
            return Result.error("请选择要删除的商品");
        }

        try {
            // 校验所有商品属于当前用户
            List<Long> userShopIds = getUserShopIds(userId);
            List<Product> products = productMapper.selectBatchIds(ids);
            for (Product product : products) {
                if (!userShopIds.contains(product.getShopId())) {
                    return Result.error("包含无权操作的商品");
                }
            }

            LambdaQueryWrapper<ProductDailyMetric> statWrapper = new LambdaQueryWrapper<>();
            statWrapper.in(ProductDailyMetric::getProductId, ids);
            statMapper.delete(statWrapper);
            deleteTrafficMetrics(ids);
            deletePricingArtifacts(ids);
            productMapper.deleteBatchIds(ids);
            return Result.success();
        } catch (Exception e) {
            log.error("Batch delete products failed", e);
            return Result.error("批量删除失败: " + e.getMessage());
        }
    }

    @Override
    public Result<ProductTrendVO> getProductTrend(Long id, int days, Long userId) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            return Result.error("商品不存在");
        }
        verifyProductOwnership(product, userId);

        LocalDate endDate = LocalDate.now();
        LocalDate startDate = endDate.minusDays(Math.max(days, 1) - 1L);
        List<ProductDailyMetric> stats = listMetrics(id, startDate, endDate);

        ProductTrendVO vo = new ProductTrendVO();
        List<String> dates = new ArrayList<>();
        List<Integer> visitors = new ArrayList<>();
        List<Integer> sales = new ArrayList<>();
        List<Double> conversionRates = new ArrayList<>();
        List<Double> avgOrderValues = new ArrayList<>();

        for (ProductDailyMetric stat : stats) {
            dates.add(stat.getStatDate().toString());
            int salesCount = defaultInteger(stat.getSalesCount());
            int visitorCount = defaultInteger(stat.getVisitorCount());
            BigDecimal turnover = defaultDecimal(stat.getTurnover());
            BigDecimal conversionRate = stat.getConversionRate() == null
                    ? calculateConversionRate(salesCount, visitorCount)
                    : stat.getConversionRate();

            visitors.add(visitorCount);
            sales.add(salesCount);
            conversionRates.add(conversionRate.doubleValue());
            if (salesCount > 0) {
                avgOrderValues.add(turnover.divide(BigDecimal.valueOf(salesCount), 2, RoundingMode.HALF_UP).doubleValue());
            } else {
                avgOrderValues.add(0.0);
            }
        }

        vo.setDates(dates);
        vo.setVisitors(visitors);
        vo.setSales(sales);
        vo.setConversionRates(conversionRates);
        vo.setAvgOrderValues(avgOrderValues);

        if (!stats.isEmpty()) {
            ProductDailyMetric lastStat = stats.get(stats.size() - 1);
            ProductDailyMetric prevDayStat = findMetricByDate(id, lastStat.getStatDate().minusDays(1));
            List<ProductDailyMetric> currentMonthStats = listMetrics(id, lastStat.getStatDate().minusDays(29), lastStat.getStatDate());
            List<ProductDailyMetric> previousMonthStats = listMetrics(id, lastStat.getStatDate().minusDays(59), lastStat.getStatDate().minusDays(30));

            int currentDailySales = defaultInteger(lastStat.getSalesCount());
            int previousDailySales = prevDayStat == null ? 0 : defaultInteger(prevDayStat.getSalesCount());
            int currentMonthlySales = sumSales(currentMonthStats);
            int previousMonthlySales = sumSales(previousMonthStats);

            BigDecimal currentDailyProfit = calculateProfit(lastStat, product.getCostPrice());
            BigDecimal previousDailyProfit = calculateProfit(prevDayStat, product.getCostPrice());
            BigDecimal currentMonthlyProfit = sumProfit(currentMonthStats, product.getCostPrice());
            BigDecimal previousMonthlyProfit = sumProfit(previousMonthStats, product.getCostPrice());

            vo.setCurrentDailySales(currentDailySales);
            vo.setCurrentMonthlySales(currentMonthlySales);
            vo.setCurrentDailyProfit(currentDailyProfit.doubleValue());
            vo.setCurrentMonthlyProfit(currentMonthlyProfit.doubleValue());

            vo.setDailySalesGrowth(currentDailySales - previousDailySales);
            vo.setDailySalesGrowthRate(calculateGrowthRate(BigDecimal.valueOf(currentDailySales), BigDecimal.valueOf(previousDailySales)));

            vo.setMonthlySalesGrowth(currentMonthlySales - previousMonthlySales);
            vo.setMonthlySalesGrowthRate(calculateGrowthRate(BigDecimal.valueOf(currentMonthlySales), BigDecimal.valueOf(previousMonthlySales)));

            vo.setDailyProfitGrowth(currentDailyProfit.subtract(previousDailyProfit).doubleValue());
            vo.setDailyProfitGrowthRate(calculateGrowthRate(currentDailyProfit, previousDailyProfit));

            vo.setMonthlyProfitGrowth(currentMonthlyProfit.subtract(previousMonthlyProfit).doubleValue());
            vo.setMonthlyProfitGrowthRate(calculateGrowthRate(currentMonthlyProfit, previousMonthlyProfit));
        }

        return Result.success(vo);
    }

    @Override
    public Result<ProductDailyMetricPageVO> getProductDailyMetrics(Long productId, Integer page, Integer size, Long userId) {
        Product product = productMapper.selectById(productId);
        if (product == null) {
            return Result.error("商品不存在");
        }
        verifyProductOwnership(product, userId);

        int safePage = page == null || page <= 0 ? 1 : page;
        int safeSize = normalizeLimit(size, 10, 50);

        LambdaQueryWrapper<ProductDailyMetric> summaryWrapper = new LambdaQueryWrapper<>();
        summaryWrapper.eq(ProductDailyMetric::getProductId, productId)
                .orderByDesc(ProductDailyMetric::getStatDate, ProductDailyMetric::getId);
        List<ProductDailyMetric> allRows = statMapper.selectList(summaryWrapper);

        LambdaQueryWrapper<ProductDailyMetric> pageWrapper = new LambdaQueryWrapper<>();
        pageWrapper.eq(ProductDailyMetric::getProductId, productId)
                .orderByDesc(ProductDailyMetric::getStatDate, ProductDailyMetric::getId);
        Page<ProductDailyMetric> resultPage = statMapper.selectPage(new Page<>(safePage, safeSize), pageWrapper);
        List<ProductDailyMetricVO> rows = resultPage.getRecords().stream()
                .map(this::toDailyMetricVO)
                .collect(Collectors.toList());
        ProductDailyMetricPageVO payload = new ProductDailyMetricPageVO();
        payload.setPage(resultPage.getCurrent());
        payload.setSize(resultPage.getSize());
        payload.setTotal(resultPage.getTotal());
        payload.setRecords(rows);
        payload.setSummary(buildDailyMetricSummary(allRows));
        return Result.success(payload);
    }

    @Override
    public Result<List<ProductSkuVO>> getProductSkus(Long productId, Long userId) {
        Product product = productMapper.selectById(productId);
        if (product == null) {
            return Result.error("商品不存在");
        }
        verifyProductOwnership(product, userId);

        LambdaQueryWrapper<ProductSku> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductSku::getProductId, productId)
                .orderByDesc(ProductSku::getUpdatedAt, ProductSku::getId);
        List<ProductSkuVO> rows = productSkuMapper.selectList(wrapper).stream()
                .map(this::toProductSkuVO)
                .collect(Collectors.toList());
        return Result.success(rows);
    }

    @Override
    public Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(Long productId, Integer limit, Long userId) {
        Product product = productMapper.selectById(productId);
        if (product == null) {
            return Result.error("商品不存在");
        }
        verifyProductOwnership(product, userId);

        int safeLimit = normalizeLimit(limit, 90, 365);
        LambdaQueryWrapper<TrafficPromoDaily> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TrafficPromoDaily::getProductId, productId)
                .orderByDesc(TrafficPromoDaily::getStatDate, TrafficPromoDaily::getId)
                .last("LIMIT " + safeLimit);
        List<TrafficPromoDailyVO> rows = trafficPromoDailyMapper.selectList(wrapper).stream()
                .map(this::toTrafficPromoVO)
                .collect(Collectors.toList());
        return Result.success(rows);
    }

    // ===== 私有辅助方法 =====

    private Product findProductByTitle(Long shopId, String title) {
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Product::getShopId, shopId)
                .eq(Product::getTitle, title)
                .last("LIMIT 1");
        return productMapper.selectOne(wrapper);
    }

    private void deleteTrafficMetrics(List<Long> productIds) {
        LambdaQueryWrapper<TrafficPromoDaily> trafficWrapper = new LambdaQueryWrapper<>();
        trafficWrapper.in(TrafficPromoDaily::getProductId, productIds);
        trafficPromoDailyMapper.delete(trafficWrapper);
    }

    private void deletePricingArtifacts(List<Long> productIds) {
        LambdaQueryWrapper<PricingTask> taskWrapper = new LambdaQueryWrapper<>();
        taskWrapper.in(PricingTask::getProductId, productIds);
        List<PricingTask> tasks = pricingTaskMapper.selectList(taskWrapper);
        if (tasks.isEmpty()) {
            return;
        }

        List<Long> taskIds = tasks.stream().map(PricingTask::getId).toList();

        LambdaQueryWrapper<AgentRunLog> logWrapper = new LambdaQueryWrapper<>();
        logWrapper.in(AgentRunLog::getTaskId, taskIds);
        agentRunLogMapper.delete(logWrapper);

        LambdaQueryWrapper<PricingResult> resultWrapper = new LambdaQueryWrapper<>();
        resultWrapper.in(PricingResult::getTaskId, taskIds);
        pricingResultMapper.delete(resultWrapper);

        LambdaQueryWrapper<PricingTask> deleteTaskWrapper = new LambdaQueryWrapper<>();
        deleteTaskWrapper.in(PricingTask::getId, taskIds);
        pricingTaskMapper.delete(deleteTaskWrapper);
    }

    private ProductMetricSummary loadMetricSummary(Long productId) {
        List<ProductDailyMetric> stats = listMetrics(productId, LocalDate.now().minusDays(29), LocalDate.now());
        int monthlySales = sumSales(stats);
        BigDecimal conversionRate = BigDecimal.ZERO;
        int count = 0;
        for (ProductDailyMetric stat : stats) {
            BigDecimal value = stat.getConversionRate() == null
                    ? calculateConversionRate(defaultInteger(stat.getSalesCount()), defaultInteger(stat.getVisitorCount()))
                    : stat.getConversionRate();
            if (value.compareTo(BigDecimal.ZERO) > 0) {
                conversionRate = conversionRate.add(value);
                count++;
            }
        }
        if (count > 0) {
            conversionRate = conversionRate.divide(BigDecimal.valueOf(count), 4, RoundingMode.HALF_UP);
        }
        return new ProductMetricSummary(monthlySales, conversionRate);
    }

    private List<ProductDailyMetric> listMetrics(Long productId, LocalDate startDate, LocalDate endDate) {
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId)
                .ge(ProductDailyMetric::getStatDate, startDate)
                .le(ProductDailyMetric::getStatDate, endDate)
                .orderByAsc(ProductDailyMetric::getStatDate);
        return statMapper.selectList(wrapper);
    }

    private ProductDailyMetric findMetricByDate(Long productId, LocalDate statDate) {
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId)
                .eq(ProductDailyMetric::getStatDate, statDate)
                .last("LIMIT 1");
        return statMapper.selectOne(wrapper);
    }

    private int sumSales(List<ProductDailyMetric> stats) {
        int total = 0;
        for (ProductDailyMetric stat : stats) {
            total += defaultInteger(stat.getSalesCount());
        }
        return total;
    }

    private BigDecimal sumProfit(List<ProductDailyMetric> stats, BigDecimal costPrice) {
        BigDecimal total = BigDecimal.ZERO;
        for (ProductDailyMetric stat : stats) {
            total = total.add(calculateProfit(stat, costPrice));
        }
        return total;
    }

    private BigDecimal calculateProfit(ProductDailyMetric stat, BigDecimal costPrice) {
        if (stat == null) {
            return BigDecimal.ZERO;
        }
        BigDecimal turnover = defaultDecimal(stat.getTurnover());
        BigDecimal cost = defaultDecimal(costPrice).multiply(BigDecimal.valueOf(defaultInteger(stat.getSalesCount())));
        return turnover.subtract(cost).setScale(2, RoundingMode.HALF_UP);
    }

    private Double calculateGrowthRate(BigDecimal current, BigDecimal previous) {
        if (previous == null || previous.compareTo(BigDecimal.ZERO) == 0) {
            return 0.0;
        }
        return current.subtract(previous)
                .divide(previous, 4, RoundingMode.HALF_UP)
                .doubleValue();
    }

    private String resolveExternalProductId(String externalProductId) {
        if (externalProductId != null && !externalProductId.isBlank()) {
            return externalProductId.trim();
        }
        return "MANUAL-" + System.currentTimeMillis();
    }

    private BigDecimal calculateConversionRate(int salesCount, int visitorCount) {
        if (visitorCount <= 0 || salesCount <= 0) {
            return BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP);
        }
        return BigDecimal.valueOf(salesCount)
                .divide(BigDecimal.valueOf(visitorCount), 4, RoundingMode.HALF_UP);
    }

    private BigDecimal defaultDecimal(BigDecimal value) {
        return value == null
                ? BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)
                : value.setScale(2, RoundingMode.HALF_UP);
    }

    private Integer defaultInteger(Integer value) {
        return value == null ? 0 : value;
    }

    private String trimToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private Page<ProductListVO> emptyPage(int current, int size) {
        Page<ProductListVO> page = new Page<>();
        page.setCurrent(current);
        page.setSize(size);
        page.setTotal(0);
        page.setRecords(List.of());
        return page;
    }

    private Map<Long, String> loadShopPlatformMap(List<Product> products) {
        if (products == null || products.isEmpty()) {
            return Collections.emptyMap();
        }
        Set<Long> shopIds = products.stream()
                .map(Product::getShopId)
                .filter(id -> id != null)
                .collect(Collectors.toSet());
        if (shopIds.isEmpty()) {
            return Collections.emptyMap();
        }
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(Shop::getId, shopIds);
        Map<Long, String> result = new HashMap<>();
        for (Shop shop : shopMapper.selectList(wrapper)) {
            result.put(shop.getId(), shop.getPlatform());
        }
        return result;
    }

    private int normalizeLimit(Integer limit, int defaultValue, int maxValue) {
        if (limit == null || limit <= 0) {
            return defaultValue;
        }
        return Math.min(limit, maxValue);
    }

    private ProductDailyMetricPageVO.Summary buildDailyMetricSummary(List<ProductDailyMetric> rows) {
        ProductDailyMetricPageVO.Summary summary = new ProductDailyMetricPageVO.Summary();
        summary.setDays(rows.size());
        summary.setTotalVisitors(rows.stream()
                .map(ProductDailyMetric::getVisitorCount)
                .filter(Objects::nonNull)
                .mapToLong(Integer::longValue)
                .sum());

        BigDecimal totalTurnover = rows.stream()
                .map(ProductDailyMetric::getTurnover)
                .filter(Objects::nonNull)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        summary.setTotalTurnover(totalTurnover);

        if (!rows.isEmpty()) {
            BigDecimal avgConversionRate = rows.stream()
                    .map(ProductDailyMetric::getConversionRate)
                    .filter(Objects::nonNull)
                    .reduce(BigDecimal.ZERO, BigDecimal::add)
                    .divide(BigDecimal.valueOf(rows.size()), 4, RoundingMode.HALF_UP);
            summary.setAvgConversionRate(avgConversionRate);
        }

        return summary;
    }

    private ProductDailyMetricVO toDailyMetricVO(ProductDailyMetric row) {
        ProductDailyMetricVO vo = new ProductDailyMetricVO();
        vo.setId(row.getId());
        vo.setStatDate(row.getStatDate());
        vo.setVisitorCount(row.getVisitorCount());
        vo.setAddCartCount(row.getAddCartCount());
        vo.setPayBuyerCount(row.getPayBuyerCount());
        vo.setSalesCount(row.getSalesCount());
        vo.setTurnover(row.getTurnover());
        vo.setRefundAmount(row.getRefundAmount());
        vo.setConversionRate(row.getConversionRate());
        vo.setCreatedAt(row.getCreatedAt());
        return vo;
    }

    private ProductSkuVO toProductSkuVO(ProductSku row) {
        ProductSkuVO vo = new ProductSkuVO();
        vo.setId(row.getId());
        vo.setExternalSkuId(row.getExternalSkuId());
        vo.setSkuName(row.getSkuName());
        vo.setSkuAttr(row.getSkuAttr());
        vo.setSalePrice(row.getSalePrice());
        vo.setCostPrice(row.getCostPrice());
        vo.setStock(row.getStock());
        vo.setUpdatedAt(row.getUpdatedAt());
        return vo;
    }

    private TrafficPromoDailyVO toTrafficPromoVO(TrafficPromoDaily row) {
        TrafficPromoDailyVO vo = new TrafficPromoDailyVO();
        vo.setId(row.getId());
        vo.setStatDate(row.getStatDate());
        vo.setTrafficSource(row.getTrafficSource());
        vo.setImpressionCount(row.getImpressionCount());
        vo.setClickCount(row.getClickCount());
        vo.setVisitorCount(row.getVisitorCount());
        vo.setCostAmount(row.getCostAmount());
        vo.setPayAmount(row.getPayAmount());
        vo.setRoi(row.getRoi());
        vo.setCreatedAt(row.getCreatedAt());
        return vo;
    }

    private Long parseLongOrNull(String value) {
        try {
            return Long.parseLong(value);
        } catch (Exception e) {
            return null;
        }
    }

    private record ProductMetricSummary(Integer monthlySales, BigDecimal conversionRate) {
    }
}
