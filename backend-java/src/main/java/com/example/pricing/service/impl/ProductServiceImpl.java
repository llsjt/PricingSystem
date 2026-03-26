package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductImportDTO;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.entity.BizProduct;
import com.example.pricing.entity.BizProductDailyStat;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.SysImportBatch;
import com.example.pricing.listener.ProductImportListener;
import com.example.pricing.mapper.BizProductDailyStatMapper;
import com.example.pricing.mapper.BizProductMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.SysImportBatchMapper;
import com.example.pricing.service.ProductService;
import com.example.pricing.vo.ProductListVO;
import com.example.pricing.vo.ProductTrendVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final BizProductMapper productMapper;
    private final SysImportBatchMapper batchMapper;
    private final BizProductDailyStatMapper statMapper;
    private final ShopMapper shopMapper;

    @Override
    public Result<String> importData(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            return Result.error("文件不能为空");
        }

        String fileName = file.getOriginalFilename();
        if (fileName == null || !fileName.matches(".*\\.(xlsx|xls)$")) {
            return Result.error("只支持 Excel 文件格式 (.xls/.xlsx)");
        }
        if (file.getSize() > 10 * 1024 * 1024) {
            return Result.error("文件大小不能超过 10MB");
        }

        Long shopId = resolveDefaultShopId();
        SysImportBatch batch = new SysImportBatch();
        batch.setShopId(shopId);
        batch.setBatchNo("BATCH-" + UUID.randomUUID());
        batch.setFileName(fileName);
        batch.setDataType("PRODUCT");
        batch.setRowCount(0);
        batch.setSuccessCount(0);
        batch.setFailCount(0);
        batch.setUploadStatus("PROCESSING");
        batchMapper.insert(batch);

        ProductImportListener listener = new ProductImportListener(this, batch.getId());
        try {
            EasyExcel.read(file.getInputStream(), ProductImportDTO.class, listener).sheet().doRead();
        } catch (IOException e) {
            log.error("Excel读取异常", e);
            batch.setUploadStatus("FAILED");
            batchMapper.updateById(batch);
            return Result.error("Excel读取失败: " + e.getMessage());
        }

        batch.setRowCount(listener.getSuccessCount() + listener.getFailCount());
        batch.setSuccessCount(listener.getSuccessCount());
        batch.setFailCount(listener.getFailCount());
        if (listener.getSuccessCount() > 0 && listener.getFailCount() > 0) {
            batch.setUploadStatus("PARTIAL_SUCCESS");
        } else if (listener.getSuccessCount() > 0) {
            batch.setUploadStatus("SUCCESS");
        } else {
            batch.setUploadStatus("FAILED");
        }
        batchMapper.updateById(batch);

        return Result.success("导入完成: 成功 " + listener.getSuccessCount() + " 行, 失败 " + listener.getFailCount() + " 行");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveImportedProduct(ProductImportDTO dto, Long batchId) {
        Long shopId = resolveDefaultShopId();
        BizProduct product = findProductByTitle(shopId, dto.getTitle());
        if (product == null) {
            product = new BizProduct();
            product.setShopId(shopId);
            product.setItemId(resolveItemId(dto.getItemId()));
            product.setStatus("ON_SALE");
            product.setTitle(dto.getTitle());
            product.setCategory(trimToNull(dto.getCategory()));
            product.setCostPrice(defaultDecimal(dto.getCostPrice()));
            product.setCurrentPrice(defaultDecimal(dto.getCurrentPrice()));
            product.setStock(defaultInteger(dto.getStock()));
            productMapper.insert(product);
        } else {
            product.setCategory(trimToNull(dto.getCategory()));
            if (dto.getCostPrice() != null) {
                product.setCostPrice(dto.getCostPrice());
            }
            if (dto.getCurrentPrice() != null) {
                product.setCurrentPrice(dto.getCurrentPrice());
            }
            if (dto.getStock() != null) {
                product.setStock(dto.getStock());
            }
            productMapper.updateById(product);
        }

        int monthlySales = safeMonthlySales(dto.getMonthlySales(), dto.getDailySales());
        BigDecimal conversionRate = resolveConversionRate(dto.getConversionRateStr(), dto.getDailySales(), dto.getDailyVisitors());
        seedRecentMetricsIfAbsent(product, monthlySales, conversionRate);
        if (dto.getDailySales() != null || dto.getDailyVisitors() != null) {
            upsertDailyMetric(product, dto.getDailySales(), dto.getDailyVisitors(), conversionRate, batchId, LocalDate.now());
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
        product.setItemId(resolveItemId(dto.getItemId()));
        product.setTitle(dto.getTitle().trim());
        product.setCategory(trimToNull(dto.getCategory()));
        product.setCostPrice(defaultDecimal(dto.getCostPrice()));
        product.setCurrentPrice(defaultDecimal(dto.getCurrentPrice()));
        product.setStock(defaultInteger(dto.getStock()));
        product.setStatus(dto.getStatus() == null || dto.getStatus().isBlank() ? "ON_SALE" : dto.getStatus().trim());
        productMapper.insert(product);

        seedRecentMetricsIfAbsent(product, safeMonthlySales(dto.getMonthlySales(), null), defaultDecimal(dto.getConversionRate()));
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
                    .or(numericKeyword != null)
                    .eq(numericKeyword != null, BizProduct::getId, numericKeyword)
                    .or(numericKeyword != null)
                    .eq(numericKeyword != null, BizProduct::getItemId, numericKeyword));
        }
        wrapper.orderByDesc(BizProduct::getUpdatedAt, BizProduct::getId);

        Page<BizProduct> productPage = productMapper.selectPage(pageParam, wrapper);
        List<ProductListVO> records = productPage.getRecords().stream().map(product -> {
            ProductMetricSummary summary = loadMetricSummary(product.getId());
            ProductListVO vo = new ProductListVO();
            vo.setId(product.getId());
            vo.setItemId(product.getItemId());
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
    public void downloadTemplate(HttpServletResponse response) {
        try {
            response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
            response.setCharacterEncoding("utf-8");
            String fileName = URLEncoder.encode("商品导入模板.xlsx", StandardCharsets.UTF_8).replaceAll("\\+", "%20");
            response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName);

            ProductImportDTO demo = new ProductImportDTO();
            demo.setItemId(202603250001L);
            demo.setTitle("示例商品 - 夏季防晒外套");
            demo.setCategory("户外服饰");
            demo.setCostPrice(new BigDecimal("68.00"));
            demo.setCurrentPrice(new BigDecimal("139.00"));
            demo.setStock(320);
            demo.setMonthlySales(260);
            demo.setConversionRateStr("4.2%");
            demo.setDailySales(11);
            demo.setDailyVisitors(260);

            EasyExcel.write(response.getOutputStream(), ProductImportDTO.class)
                    .sheet("模板")
                    .doWrite(Arrays.asList(demo));
        } catch (IOException e) {
            log.error("下载模板失败", e);
            throw new RuntimeException("下载模板失败");
        }
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
            log.error("批量删除商品失败", e);
            return Result.error("批量删除失败：" + e.getMessage());
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
        wrapper.eq(BizProduct::getShopId, shopId).eq(BizProduct::getTitle, title).last("LIMIT 1");
        return productMapper.selectOne(wrapper);
    }

    private void upsertDailyMetric(
            BizProduct product,
            Integer dailySales,
            Integer dailyVisitors,
            BigDecimal conversionRate,
            Long batchId,
            LocalDate statDate
    ) {
        LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProductDailyStat::getProductId, product.getId()).eq(BizProductDailyStat::getStatDate, statDate).last("LIMIT 1");
        BizProductDailyStat stat = statMapper.selectOne(wrapper);
        if (stat == null) {
            stat = new BizProductDailyStat();
            stat.setShopId(product.getShopId());
            stat.setProductId(product.getId());
            stat.setStatDate(statDate);
        }

        int salesCount = defaultInteger(dailySales);
        int visitorCount = defaultInteger(dailyVisitors);
        if (visitorCount == 0 && conversionRate.compareTo(BigDecimal.ZERO) > 0 && salesCount > 0) {
            visitorCount = BigDecimal.valueOf(salesCount)
                    .divide(conversionRate, 0, RoundingMode.UP)
                    .intValue();
        }

        stat.setVisitorCount(visitorCount);
        stat.setAddCartCount(Math.max(salesCount, (int) Math.round(visitorCount * 0.18)));
        stat.setPayBuyerCount(Math.max(1, salesCount));
        stat.setSalesCount(salesCount);
        stat.setTurnover(product.getCurrentPrice().multiply(BigDecimal.valueOf(salesCount)).setScale(2, RoundingMode.HALF_UP));
        stat.setRefundAmount(BigDecimal.ZERO);
        stat.setConversionRate(conversionRate.compareTo(BigDecimal.ZERO) > 0
                ? conversionRate.setScale(4, RoundingMode.HALF_UP)
                : calculateConversionRate(salesCount, visitorCount));
        stat.setUploadBatchId(batchId);

        if (stat.getId() == null) {
            statMapper.insert(stat);
        } else {
            statMapper.updateById(stat);
        }
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
            wrapper.eq(BizProductDailyStat::getProductId, product.getId()).eq(BizProductDailyStat::getStatDate, date).last("LIMIT 1");
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
        wrapper.eq(BizProductDailyStat::getProductId, productId).eq(BizProductDailyStat::getStatDate, statDate).last("LIMIT 1");
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

    private Long resolveItemId(Long itemId) {
        if (itemId != null && itemId > 0) {
            return itemId;
        }
        return System.currentTimeMillis();
    }

    private Integer safeMonthlySales(Integer monthlySales, Integer dailySales) {
        if (monthlySales != null && monthlySales > 0) {
            return monthlySales;
        }
        if (dailySales != null && dailySales > 0) {
            return dailySales * 30;
        }
        return 120;
    }

    private BigDecimal resolveConversionRate(String conversionRateText, Integer dailySales, Integer dailyVisitors) {
        BigDecimal parsed = parsePercentage(conversionRateText);
        if (parsed.compareTo(BigDecimal.ZERO) > 0) {
            return parsed;
        }
        return calculateConversionRate(defaultInteger(dailySales), defaultInteger(dailyVisitors));
    }

    private BigDecimal calculateConversionRate(int salesCount, int visitorCount) {
        if (visitorCount <= 0 || salesCount <= 0) {
            return BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP);
        }
        return BigDecimal.valueOf(salesCount)
                .divide(BigDecimal.valueOf(visitorCount), 4, RoundingMode.HALF_UP);
    }

    private BigDecimal parsePercentage(String value) {
        if (value == null || value.isBlank()) {
            return BigDecimal.ZERO;
        }
        try {
            String cleanValue = value.replace("%", "").trim();
            BigDecimal numeric = new BigDecimal(cleanValue);
            if (value.contains("%") || numeric.compareTo(BigDecimal.ONE) > 0) {
                return numeric.divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_UP);
            }
            return numeric.setScale(4, RoundingMode.HALF_UP);
        } catch (Exception e) {
            log.warn("转化率解析失败：{}", value, e);
            return BigDecimal.ZERO;
        }
    }

    private BigDecimal defaultDecimal(BigDecimal value) {
        return value == null ? BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP) : value.setScale(2, RoundingMode.HALF_UP);
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
