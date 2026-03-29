package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.ProductDailyMetric;
import com.example.pricing.entity.ProductSku;
import com.example.pricing.entity.UploadBatch;
import com.example.pricing.entity.TrafficPromoDaily;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ProductSkuMapper;
import com.example.pricing.mapper.UploadBatchMapper;
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
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class TaobaoExcelImportOutOfOrderIntegrationTest {

    @Autowired
    private TaobaoExcelImportService importService;

    @Autowired
    private ProductMapper productMapper;

    @Autowired
    private ProductDailyMetricMapper statMapper;

    @Autowired
    private ProductSkuMapper productSkuMapper;

    @Autowired
    private TrafficPromoDailyMapper trafficPromoDailyMapper;

    @Autowired
    private UploadBatchMapper batchMapper;

    @Test
    void shouldImportExcelIntoDatabaseWithoutRequiringBaseInfoFirst() throws Exception {
        String caseKey = DateTimeFormatter.ofPattern("yyMMddHHmmssSSS").format(LocalDateTime.now());
        String externalId1 = caseKey + "01";
        String externalId2 = caseKey + "02";
        String title1 = "乱序导入-防晒衣-" + caseKey;
        String title2 = "乱序导入-阔腿裤-" + caseKey;
        LocalDate statDate1 = LocalDate.of(2026, 3, 25);
        LocalDate statDate2 = LocalDate.of(2026, 3, 26);

        MockMultipartFile dailyMetricFile = createExcel(
                "tb-out-of-order-daily-" + caseKey + ".xlsx",
                "商品分析日报",
                List.of("日期", "宝贝ID", "宝贝标题", "浏览访客数", "加购人数", "支付买家数", "支付商品件数", "成交金额", "售后退款金额", "转化率"),
                List.of(
                        List.of("2026-03-25", externalId1, title1, "428", "39", "17", "21", "2289.00", "56.00", "4.91%"),
                        List.of("2026-03-26", externalId1, title1, "516", "41", "19", "23", "2507.00", "0.00", "4.46%"),
                        List.of("2026-03-25", externalId2, title2, "305", "28", "14", "16", "2064.00", "39.00", "5.25%"),
                        List.of("2026-03-26", externalId2, title2, "332", "31", "15", "18", "2322.00", "0.00", "5.42%")
                )
        );

        ImportResultVO dailyMetricResult = importService.importExcel(dailyMetricFile, "PRODUCT_DAILY_METRIC");
        assertImportResult(dailyMetricResult, "PRODUCT_DAILY_METRIC", 4, false);

        List<Product> placeholderProducts = loadProducts(externalId1, externalId2);
        assertEquals(2, placeholderProducts.size());
        assertTrue(placeholderProducts.stream().allMatch(product -> "PLACEHOLDER".equals(product.getProfileStatus())));
        assertTrue(placeholderProducts.stream().allMatch(product -> "UNKNOWN".equals(product.getStatus())));
        assertTrue(placeholderProducts.stream().allMatch(product -> product.getCurrentPrice() == null));
        assertTrue(placeholderProducts.stream().allMatch(product -> product.getCostPrice() == null));

        Map<String, Product> placeholderByExternalId = placeholderProducts.stream()
                .collect(Collectors.toMap(Product::getExternalProductId, product -> product));

        List<ProductDailyMetric> stats = statMapper.selectList(new LambdaQueryWrapper<ProductDailyMetric>()
                .in(ProductDailyMetric::getProductId, placeholderProducts.stream().map(Product::getId).toList())
                .in(ProductDailyMetric::getStatDate, List.of(statDate1, statDate2)));
        assertEquals(4, stats.size());

        MockMultipartFile trafficPromoFile = createExcel(
                "tb-out-of-order-traffic-" + caseKey + ".xlsx",
                "流量来源日报",
                List.of("数据日期", "宝贝ID", "宝贝标题", "来源渠道", "展示次数", "点击次数", "点击访客数", "消耗", "引导支付金额", "ROI"),
                List.of(
                        List.of("2026/03/25", externalId1, title1, "直通车", "18200", "824", "501", "486.30", "2721.00", "5.60"),
                        List.of("2026/03/26", externalId1, title1, "万相台", "16850", "760", "462", "420.00", "2507.00", "5.97"),
                        List.of("2026/03/25", externalId2, title2, "直通车", "14500", "628", "382", "356.50", "2215.00", "6.21"),
                        List.of("2026/03/26", externalId2, title2, "引力魔方", "13200", "577", "341", "298.40", "1886.00", "6.32")
                )
        );

        ImportResultVO trafficPromoResult = importService.importExcel(trafficPromoFile, "TRAFFIC_PROMO_DAILY");
        assertImportResult(trafficPromoResult, "TRAFFIC_PROMO_DAILY", 4, false);

        List<TrafficPromoDaily> trafficRows = trafficPromoDailyMapper.selectList(new LambdaQueryWrapper<TrafficPromoDaily>()
                .in(TrafficPromoDaily::getProductId, placeholderProducts.stream().map(Product::getId).toList())
                .in(TrafficPromoDaily::getStatDate, List.of(statDate1, statDate2)));
        assertEquals(4, trafficRows.size());
        assertTrue(trafficRows.stream().allMatch(row -> row.getProductId() != null));

        MockMultipartFile productBaseFile = createExcel(
                "tb-out-of-order-base-" + caseKey + ".xlsx",
                "宝贝列表",
                List.of("宝贝ID", "宝贝标题", "类目名称", "供货价", "一口价", "可售库存", "宝贝状态"),
                List.of(
                        List.of(externalId1, title1, "女装/外套", "58.50", "109.00", "168", "出售中"),
                        List.of(externalId2, title2, "女装/裤子", "66.00", "129.00", "124", "出售中")
                )
        );

        ImportResultVO productBaseResult = importService.importExcel(productBaseFile, "PRODUCT_BASE");
        assertImportResult(productBaseResult, "PRODUCT_BASE", 2, false);

        List<Product> finalProducts = loadProducts(externalId1, externalId2);
        assertEquals(2, finalProducts.size());
        assertEquals(
                placeholderProducts.stream().map(Product::getId).sorted().toList(),
                finalProducts.stream().map(Product::getId).sorted().toList()
        );

        Map<String, Product> productByExternalId = finalProducts.stream()
                .collect(Collectors.toMap(Product::getExternalProductId, product -> product));

        Product product1 = productByExternalId.get(externalId1);
        Product product2 = productByExternalId.get(externalId2);
        assertNotNull(product1);
        assertNotNull(product2);
        assertEquals(title1, product1.getTitle());
        assertEquals(title2, product2.getTitle());
        assertEquals("COMPLETE", product1.getProfileStatus());
        assertEquals("COMPLETE", product2.getProfileStatus());
        assertEquals("出售中", product1.getStatus());
        assertEquals("出售中", product2.getStatus());
        assertEquals(0, new BigDecimal("109.00").compareTo(product1.getCurrentPrice()));
        assertEquals(0, new BigDecimal("58.50").compareTo(product1.getCostPrice()));
        assertEquals(168, product1.getStock());
        assertEquals(0, new BigDecimal("129.00").compareTo(product2.getCurrentPrice()));
        assertEquals(0, new BigDecimal("66.00").compareTo(product2.getCostPrice()));
        assertEquals(124, product2.getStock());

        MockMultipartFile skuFile = createExcel(
                "tb-out-of-order-sku-" + caseKey + ".xlsx",
                "商品SKU",
                List.of("商品ID", "商品标题", "SKU ID", "SKU属性", "SKU售价", "SKU库存"),
                List.of(
                        List.of(externalId1, title1, externalId1 + "-BLUE-M", "颜色:蓝色;尺码:M", "109.00", "36"),
                        List.of(externalId1, title1, "", "颜色:白色;尺码:L", "", ""),
                        List.of(externalId2, title2, externalId2 + "-BLACK-S", "颜色:黑色;尺码:S", "129.00", "22")
                )
        );

        ImportResultVO skuResult = importService.importExcel(skuFile, "PRODUCT_SKU");
        assertImportResult(skuResult, "PRODUCT_SKU", 3, false);

        List<ProductSku> skuRows = productSkuMapper.selectList(new LambdaQueryWrapper<ProductSku>()
                .in(ProductSku::getProductId, finalProducts.stream().map(Product::getId).toList()));
        assertEquals(3, skuRows.size());

        ProductSku derivedSku = skuRows.stream()
                .filter(candidate -> candidate.getProductId().equals(product1.getId()) && candidate.getSkuAttr().contains("白色"))
                .findFirst()
                .orElse(null);
        assertNotNull(derivedSku);
        assertFalse(derivedSku.getExternalSkuId().isBlank());
        assertEquals(0, new BigDecimal("109.00").compareTo(derivedSku.getSalePrice()));
        assertEquals(0, new BigDecimal("58.50").compareTo(derivedSku.getCostPrice()));
        assertEquals(168, derivedSku.getStock());

        ProductDailyMetric stat = stats.stream()
                .filter(candidate -> candidate.getProductId().equals(placeholderByExternalId.get(externalId1).getId()) && candidate.getStatDate().equals(statDate1))
                .findFirst()
                .orElse(null);
        assertNotNull(stat);
        assertEquals(428, stat.getVisitorCount());
        assertEquals(0, new BigDecimal("2289.00").compareTo(stat.getTurnover()));

        TrafficPromoDaily traffic = trafficRows.stream()
                .filter(candidate -> candidate.getProductId().equals(placeholderByExternalId.get(externalId1).getId()) && "直通车".equals(candidate.getTrafficSource()))
                .findFirst()
                .orElse(null);
        assertNotNull(traffic);
        assertEquals(18200, traffic.getImpressionCount());
        assertEquals(0, new BigDecimal("0.0560").compareTo(traffic.getRoi()));

        List<UploadBatch> batches = batchMapper.selectList(new LambdaQueryWrapper<UploadBatch>()
                .in(UploadBatch::getFileName, List.of(
                        dailyMetricFile.getOriginalFilename(),
                        trafficPromoFile.getOriginalFilename(),
                        productBaseFile.getOriginalFilename(),
                        skuFile.getOriginalFilename()
                )));
        assertEquals(4, batches.size());
        assertTrue(batches.stream().allMatch(batch -> "SUCCESS".equals(batch.getUploadStatus())));
        assertTrue(batches.stream().allMatch(batch -> batch.getFailCount() == 0));

        System.out.println("OUT_OF_ORDER_IMPORT_OK caseKey=" + caseKey
                + " externalIds=" + List.of(externalId1, externalId2)
                + " productIds=" + finalProducts.stream().map(Product::getId).toList());
    }

    private List<Product> loadProducts(String... externalIds) {
        return productMapper.selectList(new LambdaQueryWrapper<Product>()
                .in(Product::getExternalProductId, List.of(externalIds)));
    }

    private void assertImportResult(ImportResultVO result, String dataType, int successCount, boolean autoDetected) {
        assertEquals(dataType, result.getDataType());
        assertEquals(successCount, result.getRowCount());
        assertEquals(successCount, result.getSuccessCount());
        assertEquals(0, result.getFailCount());
        assertEquals("SUCCESS", result.getUploadStatus());
        assertEquals(autoDetected, Boolean.TRUE.equals(result.getAutoDetected()));
        assertFalse(result.getSummary().isBlank());
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
