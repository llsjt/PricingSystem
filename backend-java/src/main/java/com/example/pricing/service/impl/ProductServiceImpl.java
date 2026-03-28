package com.example.pricing.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.ProductDailyMetric;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.TrafficPromoDaily;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import com.example.pricing.service.ProductService;
import com.example.pricing.vo.ImportResultVO;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductTrendVO;
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
import java.util.List;
import java.util.Random;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final ProductMapper productMapper;
    private final ProductDailyMetricMapper statMapper;
    private final TrafficPromoDailyMapper trafficPromoDailyMapper;
    private final PricingTaskMapper pricingTaskMapper;
    private final PricingResultMapper pricingResultMapper;
    private final AgentRunLogMapper agentRunLogMapper;
    private final ShopMapper shopMapper;
    private final TaobaoExcelImportService taobaoExcelImportService;

    @Override
    public Result<ImportResultVO> importData(MultipartFile file, String dataType) {
        try {
            return Result.success(taobaoExcelImportService.importExcel(file, dataType));
        } catch (Exception e) {
            log.error("Import excel failed", e);
            return Result.error(e.getMessage());
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<Void> addProductManual(ProductManualDTO dto) {
        Long shopId = resolveDefaultShopId();
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

        seedRecentMetricsIfAbsent(product, safeMonthlySales(dto.getMonthlySales()), defaultDecimal(dto.getConversionRate()));
        return Result.success();
    }

    @Override
    public Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource) {
        int safePage = Math.max(page, 1);
        int safeSize = size <= 0 || size > 100 ? 10 : size;

        Page<Product> pageParam = new Page<>(safePage, safeSize);
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();
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
        wrapper.orderByDesc(Product::getUpdatedAt, Product::getId);

        Page<Product> productPage = productMapper.selectPage(pageParam, wrapper);
        List<ProductListVO> records = productPage.getRecords().stream().map(product -> {
            ProductMetricSummary summary = loadMetricSummary(product.getId());
            ProductListVO vo = new ProductListVO();
            vo.setId(product.getId());
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
    public Result<Void> batchDelete(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return Result.error("请选择要删除的商品");
        }

        try {
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
    public Result<ProductTrendVO> getProductTrend(Long id, int days) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            return Result.error("商品不存在");
        }

        if (countMetrics(id) == 0) {
            generateMockTrendData(id);
        }

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
    @Transactional(rollbackFor = Exception.class)
    public void generateMockTrendData(Long productId) {
        Product product = productMapper.selectById(productId);
        if (product == null || countMetrics(productId) > 0) {
            return;
        }
        seedRecentMetrics(product, 300, new BigDecimal("0.0450"), 30);
    }

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

    private void seedRecentMetricsIfAbsent(Product product, int monthlySales, BigDecimal conversionRate) {
        if (countMetrics(product.getId()) > 0) {
            return;
        }
        seedRecentMetrics(product, monthlySales, conversionRate, 30);
    }

    private void seedRecentMetrics(Product product, int monthlySales, BigDecimal conversionRate, int days) {
        int safeMonthlySales = Math.max(monthlySales, 30);
        BigDecimal safeConversionRate = conversionRate.compareTo(BigDecimal.ZERO) > 0
                ? conversionRate
                : new BigDecimal("0.0400");
        LocalDate today = LocalDate.now();
        Random random = new Random(product.getId());
        double baseline = safeMonthlySales / (double) days;

        for (int offset = days - 1; offset >= 0; offset--) {
            LocalDate date = today.minusDays(offset);
            LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(ProductDailyMetric::getProductId, product.getId())
                    .eq(ProductDailyMetric::getStatDate, date)
                    .last("LIMIT 1");
            if (statMapper.selectOne(wrapper) != null) {
                continue;
            }

            int salesCount = Math.max(1, (int) Math.round(baseline + (offset % 7 - 3) * 0.35 + random.nextDouble() * 1.5));
            int visitorCount = BigDecimal.valueOf(salesCount)
                    .divide(safeConversionRate, 0, RoundingMode.UP)
                    .intValue();

            ProductDailyMetric stat = new ProductDailyMetric();
            stat.setShopId(product.getShopId());
            stat.setProductId(product.getId());
            stat.setStatDate(date);
            stat.setVisitorCount(visitorCount);
            stat.setAddCartCount(Math.max(salesCount, (int) Math.round(visitorCount * 0.16)));
            stat.setPayBuyerCount(Math.max(1, salesCount));
            stat.setSalesCount(salesCount);
            stat.setTurnover(product.getCurrentPrice().multiply(BigDecimal.valueOf(salesCount)).setScale(2, RoundingMode.HALF_UP));
            stat.setRefundAmount(BigDecimal.ZERO);
            stat.setConversionRate(safeConversionRate.setScale(4, RoundingMode.HALF_UP));
            statMapper.insert(stat);
        }
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

    private long countMetrics(Long productId) {
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId);
        return statMapper.selectCount(wrapper);
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

    private Long resolveDefaultShopId() {
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByAsc(Shop::getId).last("LIMIT 1");
        Shop shop = shopMapper.selectOne(wrapper);
        if (shop == null) {
            throw new IllegalStateException("未初始化默认店铺");
        }
        return shop.getId();
    }

    private String resolveExternalProductId(String externalProductId) {
        if (externalProductId != null && !externalProductId.isBlank()) {
            return externalProductId.trim();
        }
        return "MANUAL-" + System.currentTimeMillis();
    }

    private int safeMonthlySales(Integer monthlySales) {
        if (monthlySales != null && monthlySales > 0) {
            return monthlySales;
        }
        return 120;
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
