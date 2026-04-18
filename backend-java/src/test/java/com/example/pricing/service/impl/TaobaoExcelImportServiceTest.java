package com.example.pricing.service.impl;

import com.example.pricing.entity.Product;
import com.example.pricing.entity.UploadBatch;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ProductSkuMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import com.example.pricing.mapper.UploadBatchMapper;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TaobaoExcelImportServiceTest {

    @Mock
    private ProductMapper productMapper;

    @Mock
    private ProductDailyMetricMapper statMapper;

    @Mock
    private ProductSkuMapper productSkuMapper;

    @Mock
    private TrafficPromoDailyMapper trafficPromoDailyMapper;

    @Mock
    private UploadBatchMapper batchMapper;

    @Mock
    private ShopMapper shopMapper;

    private TaobaoExcelImportService service;

    @BeforeEach
    void setUp() {
        service = new TaobaoExcelImportService(
                productMapper,
                statMapper,
                productSkuMapper,
                trafficPromoDailyMapper,
                batchMapper,
                shopMapper
        );
        when(productMapper.selectOne(any())).thenReturn(null);

        AtomicLong productIds = new AtomicLong(1L);
        doAnswer(invocation -> {
            Product product = invocation.getArgument(0);
            if (product.getId() == null) {
                product.setId(productIds.getAndIncrement());
            }
            return 1;
        }).when(productMapper).insert(any(Product.class));

        doAnswer(invocation -> {
            UploadBatch batch = invocation.getArgument(0);
            batch.setId(100L);
            return 1;
        }).when(batchMapper).insert(any(UploadBatch.class));
    }

    @Test
    void productBaseImportStoresCategoryAndTitleProfileFields() throws Exception {
        MockMultipartFile file = workbookFile(
                row("\u5546\u54c1ID", "\u5546\u54c1\u6807\u9898", "\u4e00\u7ea7\u7c7b\u76ee\u540d\u79f0", "\u4e8c\u7ea7\u7c7b\u76ee\u540d\u79f0", "\u77ed\u6807\u9898", "\u526f\u6807\u9898", "\u5f53\u524d\u552e\u4ef7", "\u5e93\u5b58"),
                row("tmall-1001", "Full Product Title", "Food", "Biscuits", "Short Title", "Subtitle", "39.90", "12")
        );

        service.importExcel(file, "PRODUCT_BASE", null, 9L);

        Product product = updatedProduct();
        assertEquals("Full Product Title", product.getTitle());
        assertEquals("Food", product.getPrimaryCategoryName());
        assertEquals("Biscuits", product.getSecondaryCategoryName());
        assertEquals("Biscuits", product.getCategory());
        assertEquals("Short Title", product.getShortTitle());
        assertEquals("Subtitle", product.getSubTitle());
    }

    @Test
    void productBaseImportFallsBackToPrimaryCategoryWhenSecondaryCategoryIsBlank() throws Exception {
        MockMultipartFile file = workbookFile(
                row("\u5546\u54c1ID", "\u5546\u54c1\u6807\u9898", "\u4e00\u7ea7\u7c7b\u76ee\u540d\u79f0", "\u4e8c\u7ea7\u7c7b\u76ee\u540d\u79f0"),
                row("tmall-1002", "Second Product", "Beauty", "")
        );

        service.importExcel(file, "PRODUCT_BASE", null, 9L);

        Product product = updatedProduct();
        assertEquals("Beauty", product.getPrimaryCategoryName());
        assertNull(product.getSecondaryCategoryName());
        assertEquals("Beauty", product.getCategory());
    }

    private Product updatedProduct() {
        ArgumentCaptor<Product> productCaptor = ArgumentCaptor.forClass(Product.class);
        verify(productMapper).updateById(productCaptor.capture());
        return productCaptor.getValue();
    }

    private MockMultipartFile workbookFile(String[] headers, String[] values) throws IOException {
        try (Workbook workbook = new XSSFWorkbook();
             ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("products");
            writeRow(sheet.createRow(0), headers);
            writeRow(sheet.createRow(1), values);
            workbook.write(outputStream);
            return new MockMultipartFile(
                    "file",
                    "products.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    outputStream.toByteArray()
            );
        }
    }

    private String[] row(String... values) {
        return values;
    }

    private void writeRow(Row row, String[] values) {
        for (int i = 0; i < values.length; i++) {
            row.createCell(i).setCellValue(values[i]);
        }
    }
}
