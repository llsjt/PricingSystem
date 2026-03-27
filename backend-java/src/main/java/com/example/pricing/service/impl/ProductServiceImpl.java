package com.example.pricing.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.entity.BizProduct;
import com.example.pricing.entity.BizProductDailyStat;
import com.example.pricing.entity.Shop;
import com.example.pricing.mapper.BizProductDailyStatMapper;
import com.example.pricing.mapper.BizProductMapper;
import com.example.pricing.mapper.ShopMapper;
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

    private final BizProductMapper productMapper;
    private final BizProductDailyStatMapper statMapper;
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
        if (dto.getTitle() == null || dto.getTitle().isBlank()) {
            return Result.error("商品标题不能为空");
        }

        if (findProductByTitle(shopId, dto.getTitle()) != null) {
            return Result.error("商品名称已存在");
        }

        BizProduct product = new BizProduct();
        product.setShopId(shopId);
        product.setExternalProductId(resolveExternalProductId(dto.getItemId()));
        product.setTitle(dto.getTitle().trim());
        product.setCategory(trimToNull(dto.getCategory()));
        product.setCostPrice(defaultDecimal(dto.getCostPrice()));
        product.setCurrentPrice(defaultDecimal(dto.getCurrentPrice()));
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

        Page<BizProduct> pageParam = new Page<>(safePage, safeSize);
        LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
        if (keyword != null && !keyword.isBlank()) {
            String trimmedKeyword = keyword.trim();
            Long numericKeyword = parseLongOrNull(trimmedKeyword);
            wrapper.and(query -> query.like(BizProduct::getTitle, trimmedKeyword)
                    .or()
                    .like(BizProduct::getCategory, trimmedKeyword)
                    .or()
                    .like(BizProduct::getExternalProductId, trimmedKeyword)
                    .or(numericKeyword != null)
                    .eq(numericKeyword != null, BizProduct::getId, numericKeyword));
        }
        wrapper.orderByDesc(BizProduct::getUpdatedAt, BizProduct::getId);

        Page<BizProduct> productPage = productMapper.selectPage(pageParam, wrapper);
        List<ProductListVO> records = productPage.getRecords().stream().map(product -> {
            ProductMetricSummary summary = loadMetricSummary(product.getId());
            ProductListVO vo = new ProductListVO();
            vo.setId(product.getId());
            vo.setItemId(product.getExternalProductId());
            vo.setTitle(product.getTitle());
            vo.setCategory(product.getCategory());
            vo.setCostPrice(product.getCostPrice());
            vo.setCurrentPrice(product.getCurrentPrice());
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
            LambdaQueryWrapper<BizProductDailyStat> statWrapper = new LambdaQueryWrapper<>();
            statWrapper.in(BizProductDailyStat::getProductId, ids);
            statMapper.delete(statWrapper);
            productMapper.deleteBatchIds(ids);
            return Result.success();
        } catch (Exception e) {
            log.error("Batch delete products failed", e);
            return Result.error("批量删除失败: " + e.getMessage());
        }
    }

    @Override
    public Result<ProductTrendVO> getProductTrend(Long id, int days) {
        BizProduct product = productMapper.selectById(id);
        if (product == null) {
            return Result.error("商品不存在");
        }

        if (countMetrics(id) == 0) {
            generateMockTrendData(id);
        }

        LocalDate endDate = LocalDate.now();
        LocalDate startDate = endDate.minusDays(Math.max(days, 1) - 1L);
        List<BizProductDailyStat> stats = listMetrics(id, startDate, endDate);

        ProductTrendVO vo = new ProductTrendVO();
        List<String> dates = new ArrayList<>();
        List<Integer> visitors = new ArrayList<>();
        List<Integer> sales = new ArrayList<>();
        List<Double> conversionRates = new ArrayList<>();
        List<Double> avgOrderValues = new ArrayList<>();

        for (BizProductDailyStat stat : stats) {
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
            BizProductDailyStat lastStat = stats.get(stats.size() - 1);
            BizProductDailyStat prevDayStat = findMetricByDate(id, lastStat.getStatDate().minusDays(1));
            List<BizProductDailyStat> currentMonthStats = listMetrics(id, lastStat.getStatDate().minusDays(29), lastStat.getStatDate());
            List<BizProductDailyStat> previousMonthStats = listMetrics(id, lastStat.getStatDate().minusDays(59), lastStat.getStatDate().minusDays(30));

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
        BizProduct product = productMapper.selectById(productId);
        if (product == null || countMetrics(productId) > 0) {
            return;
        }
        seedRecentMetrics(product, 300, new BigDecimal("0.0450"), 30);
    }

    private BizProduct findProductByTitle(Long shopId, String title) {
        LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProduct::getShopId, shopId)
                .eq(BizProduct::getTitle, title)
                .last("LIMIT 1");
        return productMapper.selectOne(wrapper);
    }

    private void seedRecentMetricsIfAbsent(BizProduct product, int monthlySales, BigDecimal conversionRate) {
        if (countMetrics(product.getId()) > 0) {
            return;
        }
        seedRecentMetrics(product, monthlySales, conversionRate, 30);
    }

    private void seedRecentMetrics(BizProduct product, int monthlySales, BigDecimal conversionRate, int days) {
        int safeMonthlySales = Math.max(monthlySales, 30);
        BigDecimal safeConversionRate = conversionRate.compareTo(BigDecimal.ZERO) > 0
                ? conversionRate
                : new BigDecimal("0.0400");
        LocalDate today = LocalDate.now();
        Random random = new Random(product.getId());
        double baseline = safeMonthlySales / (double) days;

        for (int offset = days - 1; offset >= 0; offset--) {
            LocalDate date = today.minusDays(offset);
            LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(BizProductDailyStat::getProductId, product.getId())
                    .eq(BizProductDailyStat::getStatDate, date)
                    .last("LIMIT 1");
            if (statMapper.selectOne(wrapper) != null) {
                continue;
            }

            int salesCount = Math.max(1, (int) Math.round(baseline + (offset % 7 - 3) * 0.35 + random.nextDouble() * 1.5));
            int visitorCount = BigDecimal.valueOf(salesCount)
                    .divide(safeConversionRate, 0, RoundingMode.UP)
                    .intValue();

            BizProductDailyStat stat = new BizProductDailyStat();
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
        List<BizProductDailyStat> stats = listMetrics(productId, LocalDate.now().minusDays(29), LocalDate.now());
        int monthlySales = sumSales(stats);
        BigDecimal conversionRate = BigDecimal.ZERO;
        int count = 0;
        for (BizProductDailyStat stat : stats) {
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

    private List<BizProductDailyStat> listMetrics(Long productId, LocalDate startDate, LocalDate endDate) {
        LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProductDailyStat::getProductId, productId)
                .ge(BizProductDailyStat::getStatDate, startDate)
                .le(BizProductDailyStat::getStatDate, endDate)
                .orderByAsc(BizProductDailyStat::getStatDate);
        return statMapper.selectList(wrapper);
    }

    private BizProductDailyStat findMetricByDate(Long productId, LocalDate statDate) {
        LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProductDailyStat::getProductId, productId)
                .eq(BizProductDailyStat::getStatDate, statDate)
                .last("LIMIT 1");
        return statMapper.selectOne(wrapper);
    }

    private long countMetrics(Long productId) {
        LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProductDailyStat::getProductId, productId);
        return statMapper.selectCount(wrapper);
    }

    private int sumSales(List<BizProductDailyStat> stats) {
        int total = 0;
        for (BizProductDailyStat stat : stats) {
            total += defaultInteger(stat.getSalesCount());
        }
        return total;
    }

    private BigDecimal sumProfit(List<BizProductDailyStat> stats, BigDecimal costPrice) {
        BigDecimal total = BigDecimal.ZERO;
        for (BizProductDailyStat stat : stats) {
            total = total.add(calculateProfit(stat, costPrice));
        }
        return total;
    }

    private BigDecimal calculateProfit(BizProductDailyStat stat, BigDecimal costPrice) {
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
