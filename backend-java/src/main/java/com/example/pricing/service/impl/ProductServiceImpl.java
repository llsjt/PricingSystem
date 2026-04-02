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
import com.example.pricing.vo.ImportResultVO;
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
import java.util.Random;
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
    private final TaobaoExcelImportService taobaoExcelImportService;
    private final MockExcelExportService mockExcelExportService;

    /**
     * 导入商品数据，并将平台与数据类型参数转交给 Excel 导入服务处理。
     */
    @Override
    public Result<ImportResultVO> importData(MultipartFile file, String dataType, String platform) {
        try {
            if (platform == null || platform.isBlank()) {
                return Result.error("请先选择电商平台");
            }
            return Result.success(taobaoExcelImportService.importExcel(file, dataType, platform));
        } catch (Exception e) {
            log.error("Import excel failed", e);
            return Result.error(e.getMessage());
        }
    }

    @Override
    public void downloadMockExcelBundle(MockExcelExportDTO dto, HttpServletResponse response) {
        mockExcelExportService.downloadBundle(dto, response);
    }

    /**
     * 手工新增商品，并在没有历史数据时为商品补一段近期经营指标。
     */
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

        return Result.success();
    }

    /**
     * 分页查询商品列表，并补充近 30 天销量、转化率与店铺平台信息。
     */
    @Override
    public Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource, String platform) {
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
        if (platform != null && !platform.isBlank()) {
            LambdaQueryWrapper<Shop> shopWrapper = new LambdaQueryWrapper<>();
            shopWrapper.eq(Shop::getPlatform, platform.trim());
            List<Long> shopIds = shopMapper.selectList(shopWrapper).stream().map(Shop::getId).toList();
            if (shopIds.isEmpty()) {
                return Result.success(emptyPage(safePage, safeSize));
            }
            wrapper.in(Product::getShopId, shopIds);
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

    /**
     * 下载导入模板，实际模板内容由 Excel 导入服务生成。
     */
    @Override
    public void downloadTemplate(String dataType, HttpServletResponse response) {
        taobaoExcelImportService.downloadTemplate(dataType, response);
    }

    /**
     * 批量删除商品，并同步清理指标、流量和定价任务等关联数据。
     */
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

    /**
     * 生成商品趋势分析结果，包含图表序列、利润测算和环比增长。
     */
    @Override
    public Result<ProductTrendVO> getProductTrend(Long id, int days) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            return Result.error("商品不存在");
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

    /**
     * 查询商品日经营指标明细，并转换成前端需要的展示对象。
     */
    @Override
    public Result<List<ProductDailyMetricVO>> getProductDailyMetrics(Long productId, Integer limit) {
        if (productMapper.selectById(productId) == null) {
            return Result.error("商品不存在");
        }
        int safeLimit = normalizeLimit(limit, 90, 365);
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId)
                .orderByDesc(ProductDailyMetric::getStatDate, ProductDailyMetric::getId)
                .last("LIMIT " + safeLimit);
        List<ProductDailyMetricVO> rows = statMapper.selectList(wrapper).stream()
                .map(this::toDailyMetricVO)
                .collect(Collectors.toList());
        return Result.success(rows);
    }

    /**
     * 查询商品 SKU 列表。
     */
    @Override
    public Result<List<ProductSkuVO>> getProductSkus(Long productId) {
        if (productMapper.selectById(productId) == null) {
            return Result.error("商品不存在");
        }
        LambdaQueryWrapper<ProductSku> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductSku::getProductId, productId)
                .orderByDesc(ProductSku::getUpdatedAt, ProductSku::getId);
        List<ProductSkuVO> rows = productSkuMapper.selectList(wrapper).stream()
                .map(this::toProductSkuVO)
                .collect(Collectors.toList());
        return Result.success(rows);
    }

    /**
     * 查询商品流量推广日报。
     */
    @Override
    public Result<List<TrafficPromoDailyVO>> getTrafficPromoDaily(Long productId, Integer limit) {
        if (productMapper.selectById(productId) == null) {
            return Result.error("商品不存在");
        }
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



    /**
     * 按店铺和标题查找商品，避免同店铺下手工重复创建同名商品。
     */
    private Product findProductByTitle(Long shopId, String title) {
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Product::getShopId, shopId)
                .eq(Product::getTitle, title)
                .last("LIMIT 1");
        return productMapper.selectOne(wrapper);
    }

    /**
     * 删除商品对应的流量推广数据。
     */
    private void deleteTrafficMetrics(List<Long> productIds) {
        LambdaQueryWrapper<TrafficPromoDaily> trafficWrapper = new LambdaQueryWrapper<>();
        trafficWrapper.in(TrafficPromoDaily::getProductId, productIds);
        trafficPromoDailyMapper.delete(trafficWrapper);
    }

    /**
     * 删除商品关联的定价任务、结果和 Agent 日志。
     */
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



    /**
     * 汇总近 30 天销量和平均转化率，用于商品列表页展示。
     */
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

    /**
     * 按时间区间查询商品日指标。
     */
    private List<ProductDailyMetric> listMetrics(Long productId, LocalDate startDate, LocalDate endDate) {
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId)
                .ge(ProductDailyMetric::getStatDate, startDate)
                .le(ProductDailyMetric::getStatDate, endDate)
                .orderByAsc(ProductDailyMetric::getStatDate);
        return statMapper.selectList(wrapper);
    }

    /**
     * 查询商品在指定日期的单条指标记录。
     */
    private ProductDailyMetric findMetricByDate(Long productId, LocalDate statDate) {
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId)
                .eq(ProductDailyMetric::getStatDate, statDate)
                .last("LIMIT 1");
        return statMapper.selectOne(wrapper);
    }

    /**
     * 统计商品已有的指标记录数。
     */
    private long countMetrics(Long productId) {
        LambdaQueryWrapper<ProductDailyMetric> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProductDailyMetric::getProductId, productId);
        return statMapper.selectCount(wrapper);
    }

    /**
     * 汇总一组日指标中的销量。
     */
    private int sumSales(List<ProductDailyMetric> stats) {
        int total = 0;
        for (ProductDailyMetric stat : stats) {
            total += defaultInteger(stat.getSalesCount());
        }
        return total;
    }

    /**
     * 汇总一组日指标中的利润。
     */
    private BigDecimal sumProfit(List<ProductDailyMetric> stats, BigDecimal costPrice) {
        BigDecimal total = BigDecimal.ZERO;
        for (ProductDailyMetric stat : stats) {
            total = total.add(calculateProfit(stat, costPrice));
        }
        return total;
    }

    /**
     * 根据成交额、销量和成本价估算单日利润。
     */
    private BigDecimal calculateProfit(ProductDailyMetric stat, BigDecimal costPrice) {
        if (stat == null) {
            return BigDecimal.ZERO;
        }
        BigDecimal turnover = defaultDecimal(stat.getTurnover());
        BigDecimal cost = defaultDecimal(costPrice).multiply(BigDecimal.valueOf(defaultInteger(stat.getSalesCount())));
        return turnover.subtract(cost).setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * 计算环比增长率，前值为空或为零时按零处理。
     */
    private Double calculateGrowthRate(BigDecimal current, BigDecimal previous) {
        if (previous == null || previous.compareTo(BigDecimal.ZERO) == 0) {
            return 0.0;
        }
        return current.subtract(previous)
                .divide(previous, 4, RoundingMode.HALF_UP)
                .doubleValue();
    }

    /**
     * 获取默认店铺 ID，供手工新增商品和导入兜底使用。
     */
    private Long resolveDefaultShopId() {
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByAsc(Shop::getId).last("LIMIT 1");
        Shop shop = shopMapper.selectOne(wrapper);
        if (shop == null) {
            throw new IllegalStateException("未初始化默认店铺");
        }
        return shop.getId();
    }

    /**
     * 当外部商品 ID 缺失时，为手工新增商品生成内部占位 ID。
     */
    private String resolveExternalProductId(String externalProductId) {
        if (externalProductId != null && !externalProductId.isBlank()) {
            return externalProductId.trim();
        }
        return "MANUAL-" + System.currentTimeMillis();
    }

    /**
     * 根据销量和访客数计算转化率。
     */
    private BigDecimal calculateConversionRate(int salesCount, int visitorCount) {
        if (visitorCount <= 0 || salesCount <= 0) {
            return BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP);
        }
        return BigDecimal.valueOf(salesCount)
                .divide(BigDecimal.valueOf(visitorCount), 4, RoundingMode.HALF_UP);
    }

    /**
     * 将金额字段规范为两位小数，空值按零处理。
     */
    private BigDecimal defaultDecimal(BigDecimal value) {
        return value == null
                ? BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)
                : value.setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * 将整数空值统一转成零。
     */
    private Integer defaultInteger(Integer value) {
        return value == null ? 0 : value;
    }

    /**
     * 去除空白字符串，空内容时返回 null。
     */
    private String trimToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    /**
     * 构造空分页对象，用于平台筛选无数据时快速返回。
     */
    private Page<ProductListVO> emptyPage(int current, int size) {
        Page<ProductListVO> page = new Page<>();
        page.setCurrent(current);
        page.setSize(size);
        page.setTotal(0);
        page.setRecords(List.of());
        return page;
    }

    /**
     * 加载商品所属店铺的平台映射，用于列表页展示平台名称。
     */
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

    /**
     * 规范化查询条数上限，避免前端传入过大值。
     */
    private int normalizeLimit(Integer limit, int defaultValue, int maxValue) {
        if (limit == null || limit <= 0) {
            return defaultValue;
        }
        return Math.min(limit, maxValue);
    }

    /**
     * 将日经营指标实体转换为前端展示对象。
     */
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

    /**
     * 将 SKU 实体转换为前端展示对象。
     */
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

    /**
     * 将流量推广日报实体转换为前端展示对象。
     */
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

    /**
     * 尝试把关键字解析成 Long，便于支持按商品 ID 搜索。
     */
    private Long parseLongOrNull(String value) {
        try {
            return Long.parseLong(value);
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 商品列表页需要的销量与转化率摘要结构。
     */
    private record ProductMetricSummary(Integer monthlySales, BigDecimal conversionRate) {
    }
}
