package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.ProductSku;
import com.example.pricing.entity.UploadBatch;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ProductSkuMapper;
import com.example.pricing.mapper.UploadBatchMapper;
import com.example.pricing.vo.ImportResultVO;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class TaobaoExcelImportSkuFromExistingProductsIntegrationTest {

    @Autowired
    private TaobaoExcelImportService importService;

    @Autowired
    private ProductMapper productMapper;

    @Autowired
    private ProductSkuMapper productSkuMapper;

    @Autowired
    private UploadBatchMapper batchMapper;

    @Test
    void shouldImportRealisticSkuExcelBasedOnExistingProducts() throws Exception {
        String caseKey = DateTimeFormatter.ofPattern("yyMMddHHmmssSSS").format(LocalDateTime.now());
        String fallbackMarker = "type:fallback";
        String explicitMarker = "type:explicit";

        List<Product> products = productMapper.selectList(new LambdaQueryWrapper<Product>()
                .isNotNull(Product::getExternalProductId)
                .ne(Product::getExternalProductId, "")
                .orderByDesc(Product::getId)
                .last("LIMIT 3"));
        assertFalse(products.isEmpty(), "product 表暂无可用于 SKU 模拟导入的数据");

        products = products.stream()
                .filter(product -> product.getId() != null)
                .filter(product -> product.getExternalProductId() != null && !product.getExternalProductId().isBlank())
                .sorted(Comparator.comparing(Product::getId))
                .toList();
        assertFalse(products.isEmpty(), "product 表中缺少有效 external_product_id，无法模拟 SKU 导入");

        Map<Long, Product> productById = new LinkedHashMap<>();
        List<List<Object>> rows = new ArrayList<>();
        int index = 1;
        for (Product product : products) {
            productById.put(product.getId(), product);

            String externalProductId = product.getExternalProductId().trim();
            String explicitSkuId = externalProductId + "-REAL-" + caseKey + "-" + index;
            BigDecimal explicitSale = resolveExplicitSale(product);
            BigDecimal explicitCost = resolveExplicitCost(product, explicitSale);
            int explicitStock = resolveExplicitStock(product);

            rows.add(List.of(
                    externalProductId,
                    explicitSkuId,
                    "Color:Black;Size:M;Batch:" + caseKey + ";" + explicitMarker,
                    explicitSale.toPlainString(),
                    explicitCost.toPlainString(),
                    String.valueOf(explicitStock)
            ));

            rows.add(List.of(
                    externalProductId,
                    "",
                    "Color:White;Size:L;Batch:" + caseKey + ";" + fallbackMarker,
                    "",
                    "",
                    ""
            ));
            index++;
        }

        MockMultipartFile file = createExcel(
                "sku-from-existing-" + caseKey + ".xlsx",
                "SKU",
                List.of("Item ID", "SKU ID", "\u89c4\u683c", "\u4ef7\u683c", "\u6210\u672c\u4ef7", "\u5e93\u5b58"),
                rows
        );

        ImportResultVO result = importService.importExcel(file, "PRODUCT_SKU");
        assertEquals("PRODUCT_SKU", result.getDataType());
        assertEquals(rows.size(), result.getRowCount());
        assertEquals(rows.size(), result.getSuccessCount());
        assertEquals(0, result.getFailCount());
        assertEquals("SUCCESS", result.getUploadStatus());

        List<ProductSku> importedSkus = productSkuMapper.selectList(new LambdaQueryWrapper<ProductSku>()
                .like(ProductSku::getSkuAttr, "Batch:" + caseKey));
        assertEquals(rows.size(), importedSkus.size());

        for (Product product : productById.values()) {
            ProductSku fallbackSku = importedSkus.stream()
                    .filter(sku -> product.getId().equals(sku.getProductId()))
                    .filter(sku -> sku.getSkuAttr() != null && sku.getSkuAttr().contains(fallbackMarker))
                    .findFirst()
                    .orElse(null);
            assertNotNull(fallbackSku);
            assertNotNull(fallbackSku.getExternalSkuId());
            assertFalse(fallbackSku.getExternalSkuId().isBlank());
            assertTrue(fallbackSku.getExternalSkuId().startsWith(product.getExternalProductId()));
            assertEquals(0, expectedFallbackSale(product).compareTo(fallbackSku.getSalePrice()));
            assertEquals(0, expectedFallbackCost(product).compareTo(fallbackSku.getCostPrice()));
            assertEquals(expectedFallbackStock(product), fallbackSku.getStock());
        }

        List<UploadBatch> batches = batchMapper.selectList(new LambdaQueryWrapper<UploadBatch>()
                .eq(UploadBatch::getFileName, file.getOriginalFilename()));
        assertEquals(1, batches.size());
        assertEquals("SUCCESS", batches.get(0).getUploadStatus());
        assertEquals(rows.size(), batches.get(0).getSuccessCount());
    }

    private BigDecimal resolveExplicitSale(Product product) {
        if (product.getCurrentPrice() != null) {
            return product.getCurrentPrice().setScale(2, RoundingMode.HALF_UP);
        }
        return new BigDecimal("99.00");
    }

    private BigDecimal resolveExplicitCost(Product product, BigDecimal explicitSale) {
        if (product.getCostPrice() != null) {
            return product.getCostPrice().setScale(2, RoundingMode.HALF_UP);
        }
        return explicitSale.multiply(new BigDecimal("0.62")).setScale(2, RoundingMode.HALF_UP);
    }

    private int resolveExplicitStock(Product product) {
        Integer stock = product.getStock();
        if (stock != null && stock > 0) {
            return Math.max(1, stock / 2);
        }
        return 12;
    }

    private BigDecimal expectedFallbackSale(Product product) {
        if (product.getCurrentPrice() != null) {
            return product.getCurrentPrice().setScale(2, RoundingMode.HALF_UP);
        }
        return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal expectedFallbackCost(Product product) {
        if (product.getCostPrice() != null) {
            return product.getCostPrice().setScale(2, RoundingMode.HALF_UP);
        }
        BigDecimal sale = expectedFallbackSale(product);
        if (sale.compareTo(BigDecimal.ZERO) > 0) {
            return sale.multiply(new BigDecimal("0.65")).setScale(2, RoundingMode.HALF_UP);
        }
        return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    }

    private int expectedFallbackStock(Product product) {
        Integer stock = product.getStock();
        if (stock != null && stock > 0) {
            return stock;
        }
        return 0;
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
