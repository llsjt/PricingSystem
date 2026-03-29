package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.ProductDailyMetric;
import com.example.pricing.entity.ProductSku;
import com.example.pricing.entity.TrafficPromoDaily;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ProductSkuMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import com.example.pricing.vo.ImportResultVO;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class TaobaoExcelImportScenarioIntegrationTest {

    @Autowired
    private TaobaoExcelImportService importService;

    @Autowired
    private ProductMapper productMapper;

    @Autowired
    private ProductDailyMetricMapper metricMapper;

    @Autowired
    private ProductSkuMapper skuMapper;

    @Autowired
    private TrafficPromoDailyMapper trafficMapper;

    @Test
    void shouldImportInOrderSuccessfullyWithFiveRows() throws Exception {
        String caseKey = caseKey("ORDER");
        List<String> externalIds = buildExternalIds(caseKey, 5);
        List<String> titles = buildTitles(caseKey, 5);
        LocalDate statDate = LocalDate.of(2026, 3, 27);

        ImportResultVO baseResult = importService.importExcel(
                createProductBaseExcel(caseKey, externalIds, titles),
                "PRODUCT_BASE"
        );
        assertImportResult(baseResult, "PRODUCT_BASE", 5, 0, "SUCCESS");

        ImportResultVO skuResult = importService.importExcel(
                createSkuExcel(caseKey, externalIds, titles, false),
                "PRODUCT_SKU"
        );
        assertImportResult(skuResult, "PRODUCT_SKU", 5, 0, "SUCCESS");

        ImportResultVO metricResult = importService.importExcel(
                createDailyMetricExcel(caseKey, externalIds, titles, statDate, 100),
                "PRODUCT_DAILY_METRIC"
        );
        assertImportResult(metricResult, "PRODUCT_DAILY_METRIC", 5, 0, "SUCCESS");

        ImportResultVO trafficResult = importService.importExcel(
                createTrafficExcel(caseKey, externalIds, titles, statDate, 1000),
                "TRAFFIC_PROMO_DAILY"
        );
        assertImportResult(trafficResult, "TRAFFIC_PROMO_DAILY", 5, 0, "SUCCESS");

        List<Product> products = loadProductsByExternalIds(externalIds);
        assertEquals(5, products.size());
        assertTrue(products.stream().allMatch(item -> "COMPLETE".equals(item.getProfileStatus())));

        List<Long> productIds = products.stream().map(Product::getId).toList();
        List<ProductSku> skus = skuMapper.selectList(new LambdaQueryWrapper<ProductSku>()
                .in(ProductSku::getProductId, productIds));
        assertEquals(5, skus.size());

        List<ProductDailyMetric> metrics = metricMapper.selectList(new LambdaQueryWrapper<ProductDailyMetric>()
                .in(ProductDailyMetric::getProductId, productIds)
                .eq(ProductDailyMetric::getStatDate, statDate));
        assertEquals(5, metrics.size());

        List<TrafficPromoDaily> traffics = trafficMapper.selectList(new LambdaQueryWrapper<TrafficPromoDaily>()
                .in(TrafficPromoDaily::getProductId, productIds)
                .eq(TrafficPromoDaily::getStatDate, statDate));
        assertEquals(5, traffics.size());
    }

    @Test
    void shouldImportOutOfOrderSuccessfullyWithFiveRows() throws Exception {
        String caseKey = caseKey("DISORDER");
        List<String> externalIds = buildExternalIds(caseKey, 5);
        List<String> titles = buildTitles(caseKey, 5);
        LocalDate statDate = LocalDate.of(2026, 3, 28);

        ImportResultVO metricResult = importService.importExcel(
                createDailyMetricExcel(caseKey, externalIds, titles, statDate, 200),
                "PRODUCT_DAILY_METRIC"
        );
        assertImportResult(metricResult, "PRODUCT_DAILY_METRIC", 5, 0, "SUCCESS");

        List<Product> placeholders = loadProductsByExternalIds(externalIds);
        assertEquals(5, placeholders.size());
        assertTrue(placeholders.stream().allMatch(item -> "PLACEHOLDER".equals(item.getProfileStatus())));

        ImportResultVO trafficResult = importService.importExcel(
                createTrafficExcel(caseKey, externalIds, titles, statDate, 2000),
                "TRAFFIC_PROMO_DAILY"
        );
        assertImportResult(trafficResult, "TRAFFIC_PROMO_DAILY", 5, 0, "SUCCESS");

        ImportResultVO skuResult = importService.importExcel(
                createSkuExcel(caseKey, externalIds, titles, true),
                "PRODUCT_SKU"
        );
        assertImportResult(skuResult, "PRODUCT_SKU", 5, 0, "SUCCESS");

        ImportResultVO baseResult = importService.importExcel(
                createProductBaseExcel(caseKey, externalIds, titles),
                "PRODUCT_BASE"
        );
        assertImportResult(baseResult, "PRODUCT_BASE", 5, 0, "SUCCESS");

        List<Product> finalProducts = loadProductsByExternalIds(externalIds);
        assertEquals(5, finalProducts.size());
        assertTrue(finalProducts.stream().allMatch(item -> "COMPLETE".equals(item.getProfileStatus())));

        List<Long> productIds = finalProducts.stream().map(Product::getId).toList();
        assertEquals(5, skuMapper.selectCount(new LambdaQueryWrapper<ProductSku>().in(ProductSku::getProductId, productIds)));
        assertEquals(5, metricMapper.selectCount(new LambdaQueryWrapper<ProductDailyMetric>()
                .in(ProductDailyMetric::getProductId, productIds)
                .eq(ProductDailyMetric::getStatDate, statDate)));
        assertEquals(5, trafficMapper.selectCount(new LambdaQueryWrapper<TrafficPromoDaily>()
                .in(TrafficPromoDaily::getProductId, productIds)
                .eq(TrafficPromoDaily::getStatDate, statDate)));
    }

    @Test
    void shouldHandleDuplicateDataByUpdateWithoutExtraRowsWithFiveRows() throws Exception {
        String caseKey = caseKey("DUP");
        List<String> externalIds = buildExternalIds(caseKey, 5);
        List<String> titles = buildTitles(caseKey, 5);
        LocalDate statDate = LocalDate.of(2026, 3, 26);

        ImportResultVO baseResult = importService.importExcel(
                createProductBaseExcel(caseKey, externalIds, titles),
                "PRODUCT_BASE"
        );
        assertImportResult(baseResult, "PRODUCT_BASE", 5, 0, "SUCCESS");

        ImportResultVO firstImport = importService.importExcel(
                createDailyMetricExcel(caseKey, externalIds, titles, statDate, 300),
                "PRODUCT_DAILY_METRIC"
        );
        assertImportResult(firstImport, "PRODUCT_DAILY_METRIC", 5, 0, "SUCCESS");

        ImportResultVO secondImport = importService.importExcel(
                createDailyMetricExcel(caseKey, externalIds, titles, statDate, 900),
                "PRODUCT_DAILY_METRIC"
        );
        assertImportResult(secondImport, "PRODUCT_DAILY_METRIC", 5, 0, "SUCCESS");

        List<Product> products = loadProductsByExternalIds(externalIds);
        assertEquals(5, products.size());
        Map<String, Long> idByExternalId = new HashMap<>();
        for (Product item : products) {
            idByExternalId.put(item.getExternalProductId(), item.getId());
        }

        List<ProductDailyMetric> metrics = metricMapper.selectList(new LambdaQueryWrapper<ProductDailyMetric>()
                .in(ProductDailyMetric::getProductId, products.stream().map(Product::getId).toList())
                .eq(ProductDailyMetric::getStatDate, statDate));
        assertEquals(5, metrics.size());

        for (int i = 0; i < externalIds.size(); i++) {
            String externalId = externalIds.get(i);
            Long productId = idByExternalId.get(externalId);
            ProductDailyMetric metric = metrics.stream()
                    .filter(row -> row.getProductId().equals(productId))
                    .findFirst()
                    .orElse(null);
            assertNotNull(metric);
            int expectedVisitor = 900 + i;
            assertEquals(expectedVisitor, metric.getVisitorCount());
            assertEquals(0, new BigDecimal(1800 + i * 10).compareTo(metric.getTurnover()));
        }
    }

    @Test
    void shouldFailWhenImportingInvalidDataWithFiveRows() throws Exception {
        String caseKey = caseKey("INVALID");
        List<String> externalIds = buildExternalIds(caseKey, 5);
        List<String> titles = buildTitles(caseKey, 5);

        MockMultipartFile invalidMetricFile = createExcel(
                "invalid-daily-" + caseKey + ".xlsx",
                "商品经营日报",
                List.of("统计日期", "商品ID", "商品标题", "访客数", "支付件数", "支付金额"),
                List.of(
                        List.of("bad-date-1", externalIds.get(0), titles.get(0), "10", "1", "100.00"),
                        List.of("bad-date-2", externalIds.get(1), titles.get(1), "20", "2", "200.00"),
                        List.of("bad-date-3", externalIds.get(2), titles.get(2), "30", "3", "300.00"),
                        List.of("bad-date-4", externalIds.get(3), titles.get(3), "40", "4", "400.00"),
                        List.of("bad-date-5", externalIds.get(4), titles.get(4), "50", "5", "500.00")
                )
        );

        ImportResultVO result = importService.importExcel(invalidMetricFile, "PRODUCT_DAILY_METRIC");
        assertImportResult(result, "PRODUCT_DAILY_METRIC", 0, 5, "FAILED");
        assertFalse(result.getErrors() == null || result.getErrors().isEmpty());

        List<Product> products = loadProductsByExternalIds(externalIds);
        assertTrue(products.isEmpty());
    }

    private void assertImportResult(ImportResultVO result, String dataType, int successCount, int failCount, String status) {
        assertEquals(dataType, result.getDataType());
        assertEquals(successCount + failCount, result.getRowCount());
        assertEquals(successCount, result.getSuccessCount());
        assertEquals(failCount, result.getFailCount());
        assertEquals(status, result.getUploadStatus());
    }

    private String caseKey(String prefix) {
        return prefix + DateTimeFormatter.ofPattern("yyMMddHHmmssSSS").format(LocalDateTime.now());
    }

    private List<String> buildExternalIds(String caseKey, int count) {
        List<String> ids = new ArrayList<>();
        for (int i = 1; i <= count; i++) {
            ids.add(caseKey + String.format("%02d", i));
        }
        return ids;
    }

    private List<String> buildTitles(String caseKey, int count) {
        List<String> titles = new ArrayList<>();
        for (int i = 1; i <= count; i++) {
            titles.add("测试商品-" + caseKey + "-" + i);
        }
        return titles;
    }

    private MockMultipartFile createProductBaseExcel(String caseKey, List<String> externalIds, List<String> titles) throws IOException {
        List<List<Object>> rows = new ArrayList<>();
        for (int i = 0; i < externalIds.size(); i++) {
            rows.add(List.of(
                    externalIds.get(i),
                    titles.get(i),
                    i % 2 == 0 ? "女装/外套" : "女装/裤子",
                    String.format("%.2f", 50.0 + i),
                    String.format("%.2f", 100.0 + i),
                    String.valueOf(120 + i),
                    "出售中"
            ));
        }
        return createExcel(
                "ordered-base-" + caseKey + ".xlsx",
                "商品基础信息",
                List.of("商品ID", "商品标题", "商品类目", "成本价", "当前售价", "库存", "商品状态"),
                rows
        );
    }

    private MockMultipartFile createSkuExcel(String caseKey, List<String> externalIds, List<String> titles, boolean leaveSkuIdEmpty) throws IOException {
        List<List<Object>> rows = new ArrayList<>();
        for (int i = 0; i < externalIds.size(); i++) {
            rows.add(List.of(
                    externalIds.get(i),
                    titles.get(i),
                    leaveSkuIdEmpty ? "" : externalIds.get(i) + "-SKU-" + (i + 1),
                    "颜色:黑色;尺码:" + (i % 2 == 0 ? "M" : "L"),
                    String.format("%.2f", 100.0 + i),
                    String.valueOf(30 + i)
            ));
        }
        return createExcel(
                "ordered-sku-" + caseKey + ".xlsx",
                "商品SKU",
                List.of("商品ID", "商品标题", "SKU ID", "SKU属性", "SKU售价", "SKU库存"),
                rows
        );
    }

    private MockMultipartFile createDailyMetricExcel(
            String caseKey,
            List<String> externalIds,
            List<String> titles,
            LocalDate statDate,
            int visitorBase
    ) throws IOException {
        List<List<Object>> rows = new ArrayList<>();
        for (int i = 0; i < externalIds.size(); i++) {
            rows.add(List.of(
                    statDate.toString(),
                    externalIds.get(i),
                    titles.get(i),
                    String.valueOf(visitorBase + i),
                    String.valueOf(10 + i),
                    String.valueOf(1800 + i * 10)
            ));
        }
        return createExcel(
                "daily-" + caseKey + ".xlsx",
                "商品经营日报",
                List.of("统计日期", "商品ID", "商品标题", "访客数", "支付件数", "支付金额"),
                rows
        );
    }

    private MockMultipartFile createTrafficExcel(
            String caseKey,
            List<String> externalIds,
            List<String> titles,
            LocalDate statDate,
            int impressionBase
    ) throws IOException {
        List<List<Object>> rows = new ArrayList<>();
        for (int i = 0; i < externalIds.size(); i++) {
            rows.add(List.of(
                    statDate.toString(),
                    externalIds.get(i),
                    titles.get(i),
                    i % 2 == 0 ? "直通车" : "引力魔方",
                    String.valueOf(impressionBase + i * 100),
                    String.valueOf(100 + i),
                    String.valueOf(80 + i),
                    String.format("%.2f", 300.0 + i),
                    String.format("%.2f", 1600.0 + i * 10),
                    String.format("%.2f", 5.2 + i * 0.1)
            ));
        }
        return createExcel(
                "traffic-" + caseKey + ".xlsx",
                "流量推广日报",
                List.of("统计日期", "商品ID", "商品标题", "流量来源", "展现量", "点击量", "访客数", "花费", "支付金额", "ROI"),
                rows
        );
    }

    private List<Product> loadProductsByExternalIds(List<String> externalIds) {
        return productMapper.selectList(new LambdaQueryWrapper<Product>()
                .in(Product::getExternalProductId, externalIds));
    }

    private MockMultipartFile createExcel(
            String fileName,
            String sheetName,
            List<String> headers,
            List<List<Object>> rows
    ) throws IOException {
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        EasyExcel.write(outputStream)
                .head(headers.stream().map(List::of).toList())
                .sheet(sheetName)
                .doWrite(rows);
        return new MockMultipartFile(
                "file",
                fileName,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                outputStream.toByteArray()
        );
    }
}
