package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.ProductImportDTO;
import com.example.pricing.dto.ProductManualDTO;
import com.example.pricing.entity.BizProduct;
import com.example.pricing.entity.SysImportBatch;
import com.example.pricing.listener.ProductImportListener;
import com.example.pricing.mapper.BizProductMapper;
import com.example.pricing.mapper.SysImportBatchMapper;
import com.example.pricing.service.ProductService;
import com.example.pricing.vo.ProductListVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.Arrays;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final BizProductMapper productMapper;
    private final SysImportBatchMapper batchMapper;
    private final com.example.pricing.mapper.BizProductDailyStatMapper statMapper;

    @Override
    public Result<String> importData(MultipartFile file) {
        if (file.isEmpty()) {
            return Result.error("文件不能为空");
        }

        // 校验文件类型
        String fileName = file.getOriginalFilename();
        if (fileName == null || !fileName.matches(".*\\.(xlsx|xls)$")) {
            return Result.error("只支持 Excel 文件格式 (.xls/.xlsx)");
        }

        // 校验文件大小 (不超过 10MB)
        if (file.getSize() > 10 * 1024 * 1024) {
            return Result.error("文件大小不能超过 10MB");
        }

        // 1. 创建导入批次记录
        SysImportBatch batch = new SysImportBatch();
        batch.setBatchNo(UUID.randomUUID().toString());
        batch.setFileName(fileName);
        batch.setSuccessCount(0);
        batch.setFailCount(0);
        batchMapper.insert(batch);

        // 2. 使用 EasyExcel 读取并处理数据
        ProductImportListener listener = new ProductImportListener(this, batch.getId());
        try {
            EasyExcel.read(file.getInputStream(), ProductImportDTO.class, listener).sheet().doRead();
        } catch (IOException e) {
            log.error("Excel读取异常", e);
            return Result.error("Excel读取失败: " + e.getMessage());
        }

        // 3. 更新批次结果
        batch.setSuccessCount(listener.getSuccessCount());
        batch.setFailCount(listener.getFailCount());
        String errorLog = String.join("\n", listener.getErrorMessages());
        if (errorLog != null && errorLog.length() > 65535) {
            errorLog = errorLog.substring(0, 65535);
        }
        batch.setErrorLog(errorLog);
        batchMapper.updateById(batch);

        return Result.success("导入完成: 成功 " + listener.getSuccessCount() + " 行, 失败 " + listener.getFailCount() + " 行");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveImportedProduct(ProductImportDTO data, Long batchId) {
        // 根据商品标题查询是否已存在
        LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProduct::getTitle, data.getTitle());
        BizProduct existing = productMapper.selectOne(wrapper);

        BizProduct product;
        if (existing == null) {
            // 新增商品
            product = new BizProduct();
            product.setTitle(data.getTitle());
            product.setCategory(data.getCategory());
            product.setCostPrice(data.getCostPrice() != null ? data.getCostPrice() : BigDecimal.ZERO);
            product.setMarketPrice(data.getMarketPrice());
            product.setCurrentPrice(data.getCurrentPrice() != null ? data.getCurrentPrice() : BigDecimal.ZERO);
            product.setStock(data.getStock() != null ? data.getStock() : 0);
            product.setMonthlySales(data.getMonthlySales() != null ? data.getMonthlySales() : 0);
            product.setSource("IMPORT");
            
            // 处理百分比字段
            product.setClickRate(parsePercentage(data.getClickRateStr()));
            product.setConversionRate(parsePercentage(data.getConversionRateStr()));
            
            productMapper.insert(product);
        } else {
            // 更新现有商品
            product = existing;
            product.setTitle(data.getTitle());
            product.setCategory(data.getCategory());
            product.setCostPrice(data.getCostPrice() != null ? data.getCostPrice() : product.getCostPrice());
            product.setMarketPrice(data.getMarketPrice());
            product.setCurrentPrice(data.getCurrentPrice() != null ? data.getCurrentPrice() : product.getCurrentPrice());
            product.setStock(data.getStock() != null ? data.getStock() : product.getStock());
            product.setMonthlySales(data.getMonthlySales() != null ? data.getMonthlySales() : product.getMonthlySales());
            
            if (data.getClickRateStr() != null) {
                product.setClickRate(parsePercentage(data.getClickRateStr()));
            }
            if (data.getConversionRateStr() != null) {
                product.setConversionRate(parsePercentage(data.getConversionRateStr()));
            }
            
            productMapper.updateById(product);
        }
        
        // 保存日统计数据 (如果有)
        if (data.getDailySales() != null || data.getDailyVisitors() != null) {
            saveDailyStat(product.getId(), data);
        }
    }
    
    private void saveDailyStat(Long productId, ProductImportDTO data) {
        java.time.LocalDate today = java.time.LocalDate.now();
        
        // 检查今日是否已存在
        LambdaQueryWrapper<com.example.pricing.entity.BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getProductId, productId);
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getStatDate, today);
        com.example.pricing.entity.BizProductDailyStat existingStat = statMapper.selectOne(wrapper);
        
        if (existingStat == null) {
            com.example.pricing.entity.BizProductDailyStat stat = new com.example.pricing.entity.BizProductDailyStat();
            stat.setProductId(productId);
            stat.setStatDate(today);
            stat.setSalesCount(data.getDailySales() != null ? data.getDailySales() : 0);
            // Visitor and conversion metrics are not stored in the current table schema.
            
            // 计算转化率和销售额
            if (stat.getVisitorCount() > 0) {
                BigDecimal cr = new BigDecimal(stat.getSalesCount()).divide(new BigDecimal(stat.getVisitorCount()), 4, java.math.RoundingMode.HALF_UP);
                // No-op: conversion rate is derived in-memory when needed.
            } else {
                // No-op: conversion rate is derived in-memory when needed.
            }
            
            // 获取最新价格计算销售额
            BizProduct product = productMapper.selectById(productId);
            if (product != null && product.getCurrentPrice() != null) {
                stat.setTurnover(product.getCurrentPrice().multiply(new BigDecimal(stat.getSalesCount())));
            } else {
                stat.setTurnover(BigDecimal.ZERO);
            }
            
            statMapper.insert(stat);
        } else {
            // 更新今日数据
            if (data.getDailySales() != null) existingStat.setSalesCount(data.getDailySales());
            // Visitor and conversion metrics are not stored in the current table schema.
            
            if (existingStat.getVisitorCount() > 0) {
                BigDecimal cr = new BigDecimal(existingStat.getSalesCount()).divide(new BigDecimal(existingStat.getVisitorCount()), 4, java.math.RoundingMode.HALF_UP);
                // No-op: conversion rate is derived in-memory when needed.
            }
            
            BizProduct product = productMapper.selectById(productId);
            if (product != null && product.getCurrentPrice() != null) {
                existingStat.setTurnover(product.getCurrentPrice().multiply(new BigDecimal(existingStat.getSalesCount())));
            }
            
            statMapper.updateById(existingStat);
        }
    }

    private BigDecimal parsePercentage(String str) {
        if (str == null || str.trim().isEmpty()) {
            return BigDecimal.ZERO;
        }
        try {
            String cleanStr = str.replace("%", "").trim();
            BigDecimal val = new BigDecimal(cleanStr);
            // 如果原字符串包含%，说明是百分比格式，需要除以 100
            // 否则假设已经是小数形式 (如 0.12)
            if (str.contains("%")) {
                return val.divide(new BigDecimal("100"));
            }
            // 对于没有%的数字，如果大于 1，假设是百分比数值 (如 50 代表 50%)
            if (val.compareTo(BigDecimal.ONE) > 0) {
                return val.divide(new BigDecimal("100"));
            }
            return val;
        } catch (Exception e) {
            log.warn("百分比解析失败：{}", str, e);
            return BigDecimal.ZERO;
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<Void> addProductManual(ProductManualDTO dto) {
        // 校验商品标题是否重复
        LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProduct::getTitle, dto.getTitle());
        Long count = productMapper.selectCount(wrapper);
        if (count > 0) {
            return Result.error("商品名称已存在");
        }

        BizProduct product = new BizProduct();
        product.setTitle(dto.getTitle());
        product.setCategory(dto.getCategory());
        product.setCostPrice(dto.getCostPrice());
        product.setMarketPrice(dto.getMarketPrice());
        product.setCurrentPrice(dto.getCurrentPrice());
        product.setStock(dto.getStock());
        product.setMonthlySales(dto.getMonthlySales() != null ? dto.getMonthlySales() : 0);
        product.setClickRate(dto.getClickRate() != null ? dto.getClickRate() : BigDecimal.ZERO);
        product.setConversionRate(dto.getConversionRate() != null ? dto.getConversionRate() : BigDecimal.ZERO);
        product.setSource(dto.getSource());
        
        productMapper.insert(product);
        return Result.success();
    }

    @Override
    public Result<Page<ProductListVO>> getProductList(int page, int size, String keyword, String dataSource) {
        // 校验分页参数
        if (page <= 0) {
            page = 1;
        }
        if (size <= 0 || size > 100) {
            size = 10; // 默认每页 10 条，最大 100 条
        }

        Page<BizProduct> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
        
        // 关键词搜索 (标题或ID)
        if (keyword != null && !keyword.isEmpty()) {
            wrapper.and(w -> w.like(BizProduct::getTitle, keyword).or().eq(BizProduct::getId, keyword));
        }
        // 数据来源筛选
        if (dataSource != null && !dataSource.isEmpty()) {
            wrapper.eq(BizProduct::getSource, dataSource);
        }
        
        wrapper.orderByDesc(BizProduct::getUpdatedAt);

        Page<BizProduct> productPage = productMapper.selectPage(pageParam, wrapper);

        Page<ProductListVO> resultPage = new Page<>();
        resultPage.setCurrent(productPage.getCurrent());
        resultPage.setSize(productPage.getSize());
        resultPage.setTotal(productPage.getTotal());

        // 转换 Entity -> VO
        List<ProductListVO> voList = productPage.getRecords().stream().map(p -> {
            ProductListVO vo = new ProductListVO();
            vo.setId(p.getId());
            vo.setTitle(p.getTitle());
            vo.setCategory(p.getCategory());
            vo.setCostPrice(p.getCostPrice());
            vo.setMarketPrice(p.getMarketPrice());
            vo.setCurrentPrice(p.getCurrentPrice());
            vo.setStock(p.getStock());
            vo.setSource(p.getSource());
            vo.setMonthlySales(p.getMonthlySales());
            vo.setClickRate(p.getClickRate());
            vo.setConversionRate(p.getConversionRate());
            vo.setUpdatedAt(p.getUpdatedAt());
            return vo;
        }).collect(Collectors.toList());

        resultPage.setRecords(voList);
        return Result.success(resultPage);
    }

    @Override
    public void downloadTemplate(HttpServletResponse response) {
        try {
            response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
            response.setCharacterEncoding("utf-8");
            String fileName = URLEncoder.encode("商品导入模板.xlsx", StandardCharsets.UTF_8).replaceAll("\\+", "%20");
            response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName);

            // 创建示例数据
            ProductImportDTO demo = new ProductImportDTO();
            demo.setTitle("示例商品 - 夏季 T 恤");
            demo.setCategory("男装");
            demo.setCostPrice(new BigDecimal("30.00"));
            demo.setMarketPrice(new BigDecimal("99.00"));
            demo.setCurrentPrice(new BigDecimal("59.00"));
            demo.setStock(1000);
            demo.setMonthlySales(500);
            demo.setClickRateStr("5.5%");
            demo.setConversionRateStr("1.2%");
            demo.setDailySales(20);
            demo.setDailyVisitors(200);

            EasyExcel.write(response.getOutputStream(), ProductImportDTO.class).sheet("模板").doWrite(Arrays.asList(demo));
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
            // 使用 MyBatis-Plus 的 deleteBatchIds 方法批量删除
            int deletedCount = productMapper.deleteBatchIds(ids);
            log.info("批量删除商品成功，删除数量：{}", deletedCount);
            return Result.success();
        } catch (Exception e) {
            log.error("批量删除商品失败", e);
            return Result.error("批量删除失败：" + e.getMessage());
        }
    }

    @Override
    public Result<com.example.pricing.vo.ProductTrendVO> getProductTrend(Long id, int days) {
        // 1. Check if product exists
        BizProduct product = productMapper.selectById(id);
        if (product == null) {
            return Result.error("商品不存在");
        }
        
        // 2. Query stats
        java.time.LocalDate endDate = java.time.LocalDate.now();
        java.time.LocalDate startDate = endDate.minusDays(days - 1);
        
        LambdaQueryWrapper<com.example.pricing.entity.BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getProductId, id);
        wrapper.ge(com.example.pricing.entity.BizProductDailyStat::getStatDate, startDate);
        wrapper.le(com.example.pricing.entity.BizProductDailyStat::getStatDate, endDate);
        wrapper.orderByAsc(com.example.pricing.entity.BizProductDailyStat::getStatDate);
        
        List<com.example.pricing.entity.BizProductDailyStat> stats = statMapper.selectList(wrapper);
        
        // 3. Transform to VO
        com.example.pricing.vo.ProductTrendVO vo = new com.example.pricing.vo.ProductTrendVO();
        List<String> dates = new ArrayList<>();
        List<Integer> visitors = new ArrayList<>();
        List<Integer> sales = new ArrayList<>();
        List<Double> conversionRates = new ArrayList<>();
        List<Double> avgOrderValues = new ArrayList<>(); // Turnover / Sales
        
        for (com.example.pricing.entity.BizProductDailyStat stat : stats) {
            dates.add(stat.getStatDate().toString());
            visitors.add(0);
            sales.add(stat.getSalesCount() != null ? stat.getSalesCount() : 0);
            conversionRates.add(0.0);
            
            if (stat.getSalesCount() > 0 && stat.getTurnover() != null) {
                avgOrderValues.add(stat.getTurnover().divide(new BigDecimal(stat.getSalesCount()), 2, java.math.RoundingMode.HALF_UP).doubleValue());
            } else {
                avgOrderValues.add(0.0);
            }
        }
        
        vo.setDates(dates);
        vo.setVisitors(visitors);
        vo.setSales(sales);
        vo.setConversionRates(conversionRates);
        vo.setAvgOrderValues(avgOrderValues);
        
        // Calculate insights
        if (!stats.isEmpty()) {
            // Current day (or last available day)
            com.example.pricing.entity.BizProductDailyStat lastStat = stats.get(stats.size() - 1);
            java.time.LocalDate lastDate = lastStat.getStatDate();
            
            // Previous day
            com.example.pricing.entity.BizProductDailyStat prevDayStat = findStatByDate(id, lastDate.minusDays(1));

            // 30-day and previous 30-day windows for absolute monthly values and month-over-month growth.
            List<com.example.pricing.entity.BizProductDailyStat> currentMonthStats =
                    findStatsByRange(id, lastDate.minusDays(29), lastDate);
            List<com.example.pricing.entity.BizProductDailyStat> previousMonthStats =
                    findStatsByRange(id, lastDate.minusDays(59), lastDate.minusDays(30));

            // Profit Calculation (Turnover - Cost * Sales)
            BigDecimal costPrice = product.getCostPrice() != null ? product.getCostPrice() : BigDecimal.ZERO;

            int currentDailySales = lastStat.getSalesCount() != null ? lastStat.getSalesCount() : 0;
            int prevDaySales = prevDayStat != null && prevDayStat.getSalesCount() != null ? prevDayStat.getSalesCount() : 0;
            int currentMonthlySales = sumSales(currentMonthStats);
            int previousMonthlySales = sumSales(previousMonthStats);

            BigDecimal currentDailyProfit = calculateProfit(lastStat, costPrice);
            BigDecimal prevDayProfit = calculateProfit(prevDayStat, costPrice);
            BigDecimal currentMonthlyProfit = sumProfit(currentMonthStats, costPrice);
            BigDecimal previousMonthlyProfit = sumProfit(previousMonthStats, costPrice);

            // Current absolute values (for dashboard cards)
            vo.setCurrentDailySales(currentDailySales);
            vo.setCurrentMonthlySales(currentMonthlySales);
            vo.setCurrentDailyProfit(currentDailyProfit.doubleValue());
            vo.setCurrentMonthlyProfit(currentMonthlyProfit.doubleValue());

            // Daily Sales Growth
            vo.setDailySalesGrowth(currentDailySales - prevDaySales);
            vo.setDailySalesGrowthRate(calculateGrowthRate(new BigDecimal(currentDailySales), new BigDecimal(prevDaySales)));

            // Monthly Sales Growth
            vo.setMonthlySalesGrowth(currentMonthlySales - previousMonthlySales);
            vo.setMonthlySalesGrowthRate(calculateGrowthRate(new BigDecimal(currentMonthlySales), new BigDecimal(previousMonthlySales)));

            // Daily Profit Growth
            vo.setDailyProfitGrowth(currentDailyProfit.subtract(prevDayProfit).doubleValue());
            vo.setDailyProfitGrowthRate(calculateGrowthRate(currentDailyProfit, prevDayProfit));

            // Monthly Profit Growth
            vo.setMonthlyProfitGrowth(currentMonthlyProfit.subtract(previousMonthlyProfit).doubleValue());
            vo.setMonthlyProfitGrowthRate(calculateGrowthRate(currentMonthlyProfit, previousMonthlyProfit));
        }
        
        return Result.success(vo);
    }

    private com.example.pricing.entity.BizProductDailyStat findStatByDate(Long productId, java.time.LocalDate date) {
        LambdaQueryWrapper<com.example.pricing.entity.BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getProductId, productId);
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getStatDate, date);
        return statMapper.selectOne(wrapper);
    }

    private List<com.example.pricing.entity.BizProductDailyStat> findStatsByRange(
            Long productId,
            java.time.LocalDate startDate,
            java.time.LocalDate endDate
    ) {
        LambdaQueryWrapper<com.example.pricing.entity.BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getProductId, productId);
        wrapper.ge(com.example.pricing.entity.BizProductDailyStat::getStatDate, startDate);
        wrapper.le(com.example.pricing.entity.BizProductDailyStat::getStatDate, endDate);
        return statMapper.selectList(wrapper);
    }

    private int sumSales(List<com.example.pricing.entity.BizProductDailyStat> stats) {
        int total = 0;
        for (com.example.pricing.entity.BizProductDailyStat stat : stats) {
            total += stat.getSalesCount() != null ? stat.getSalesCount() : 0;
        }
        return total;
    }

    private BigDecimal sumProfit(List<com.example.pricing.entity.BizProductDailyStat> stats, BigDecimal costPrice) {
        BigDecimal total = BigDecimal.ZERO;
        for (com.example.pricing.entity.BizProductDailyStat stat : stats) {
            total = total.add(calculateProfit(stat, costPrice));
        }
        return total;
    }

    private Double calculateGrowthRate(BigDecimal current, BigDecimal previous) {
        if (previous == null || previous.compareTo(BigDecimal.ZERO) == 0) {
            return 0.0;
        }
        return current.subtract(previous)
                .divide(previous, 4, java.math.RoundingMode.HALF_UP)
                .doubleValue();
    }
    
    private BigDecimal calculateProfit(com.example.pricing.entity.BizProductDailyStat stat, BigDecimal costPrice) {
        if (stat == null) return BigDecimal.ZERO;
        BigDecimal turnover = stat.getTurnover() != null ? stat.getTurnover() : BigDecimal.ZERO;
        BigDecimal safeCostPrice = costPrice != null ? costPrice : BigDecimal.ZERO;
        int salesCount = stat.getSalesCount() != null ? stat.getSalesCount() : 0;
        BigDecimal cost = safeCostPrice.multiply(new BigDecimal(salesCount));
        return turnover.subtract(cost);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void generateMockTrendData(Long productId) {
        // Generate data for past 90 days
        java.time.LocalDate today = java.time.LocalDate.now();
        java.util.Random random = new java.util.Random();
        
        // Check if data exists to avoid duplicates
        LambdaQueryWrapper<com.example.pricing.entity.BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.BizProductDailyStat::getProductId, productId);
        if (statMapper.selectCount(wrapper) > 0) return;
        
        for (int i = 90; i >= 0; i--) {
            java.time.LocalDate date = today.minusDays(i);
            
            com.example.pricing.entity.BizProductDailyStat stat = new com.example.pricing.entity.BizProductDailyStat();
            stat.setProductId(productId);
            stat.setStatDate(date);
            
            int visitors = 500 + random.nextInt(1000); // 500-1500
            double cr = 0.02 + random.nextDouble() * 0.05; // 2% - 7%
            int sales = (int) (visitors * cr);
            BigDecimal price = new BigDecimal(50 + random.nextInt(50)); // 50-100 price
            BigDecimal turnover = price.multiply(new BigDecimal(sales));
            
            // Visitor data is not stored in the current table schema.
            stat.setSalesCount(sales);
            stat.setTurnover(turnover);
            // Conversion rate is not stored in the current table schema.
            
            statMapper.insert(stat);
        }
    }
}
