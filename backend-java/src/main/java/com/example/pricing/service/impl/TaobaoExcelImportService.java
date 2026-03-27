package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.BizProduct;
import com.example.pricing.entity.BizProductDailyStat;
import com.example.pricing.entity.Shop;
import com.example.pricing.entity.SysImportBatch;
import com.example.pricing.entity.TrafficPromoDaily;
import com.example.pricing.mapper.BizProductDailyStatMapper;
import com.example.pricing.mapper.BizProductMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.SysImportBatchMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import com.example.pricing.vo.ImportResultVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.FormulaEvaluator;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class TaobaoExcelImportService {

    private static final long MAX_FILE_SIZE = 10 * 1024 * 1024L;

    private final BizProductMapper productMapper;
    private final BizProductDailyStatMapper statMapper;
    private final TrafficPromoDailyMapper trafficPromoDailyMapper;
    private final SysImportBatchMapper batchMapper;
    private final ShopMapper shopMapper;

    @Transactional(rollbackFor = Exception.class)
    public ImportResultVO importExcel(MultipartFile file, String requestedTypeCode) {
        validateFile(file);
        ParsedSheet sheet = parseSheet(file);
        if (sheet.rows().isEmpty()) {
            throw new IllegalArgumentException("Excel 未读取到可导入的数据行");
        }

        ImportType resolvedType = resolveImportType(requestedTypeCode, sheet.headers());
        boolean autoDetected = requestedTypeCode == null
                || requestedTypeCode.isBlank()
                || "AUTO".equalsIgnoreCase(requestedTypeCode);

        Long shopId = resolveDefaultShopId();
        SysImportBatch batch = createBatch(
                shopId,
                Objects.requireNonNullElse(file.getOriginalFilename(), "taobao-import.xlsx"),
                resolvedType
        );

        int successCount = 0;
        int failCount = 0;
        LocalDate minDate = null;
        LocalDate maxDate = null;
        List<String> errors = new ArrayList<>();

        for (ParsedRow row : sheet.rows()) {
            try {
                LocalDate rowDate = switch (resolvedType) {
                    case PRODUCT_BASE -> importProductBase(shopId, row);
                    case PRODUCT_DAILY_METRIC -> importProductDailyMetric(shopId, batch.getId(), row);
                    case TRAFFIC_PROMO_DAILY -> importTrafficPromoDaily(shopId, batch.getId(), row);
                };
                successCount++;
                if (rowDate != null) {
                    minDate = minDate == null || rowDate.isBefore(minDate) ? rowDate : minDate;
                    maxDate = maxDate == null || rowDate.isAfter(maxDate) ? rowDate : maxDate;
                }
            } catch (Exception e) {
                failCount++;
                String error = "第 " + row.rowNumber() + " 行导入失败: " + e.getMessage();
                if (errors.size() < 10) {
                    errors.add(error);
                }
                log.warn("Import row failed, type={}, row={}", resolvedType.code, row.rowNumber(), e);
            }
        }

        int rowCount = successCount + failCount;
        batch.setRowCount(rowCount);
        batch.setSuccessCount(successCount);
        batch.setFailCount(failCount);
        batch.setStartDate(minDate);
        batch.setEndDate(maxDate);
        if (successCount > 0 && failCount > 0) {
            batch.setUploadStatus("PARTIAL_SUCCESS");
        } else if (successCount > 0) {
            batch.setUploadStatus("SUCCESS");
        } else {
            batch.setUploadStatus("FAILED");
        }
        batchMapper.updateById(batch);

        ImportResultVO result = new ImportResultVO();
        result.setDataType(resolvedType.code);
        result.setDataTypeLabel(resolvedType.label);
        result.setTargetTable(resolvedType.targetTable);
        result.setFileName(batch.getFileName());
        result.setRowCount(rowCount);
        result.setSuccessCount(successCount);
        result.setFailCount(failCount);
        result.setUploadStatus(batch.getUploadStatus());
        result.setStartDate(minDate);
        result.setEndDate(maxDate);
        result.setAutoDetected(autoDetected);
        result.setErrors(errors);
        result.setSummary(buildSummary(resolvedType, successCount, failCount, autoDetected));
        return result;
    }

    public void downloadTemplate(String requestedTypeCode, HttpServletResponse response) {
        ImportType importType = resolveTemplateType(requestedTypeCode);
        try {
            response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
            response.setCharacterEncoding("utf-8");
            String fileName = URLEncoder.encode(importType.templateFileName, StandardCharsets.UTF_8)
                    .replaceAll("\\+", "%20");
            response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName);

            EasyExcel.write(response.getOutputStream())
                    .head(importType.templateHead())
                    .sheet(importType.sheetName)
                    .doWrite(importType.templateRows());
        } catch (IOException e) {
            log.error("Download template failed, type={}", importType.code, e);
            throw new RuntimeException("下载模板失败");
        }
    }

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("文件不能为空");
        }
        String fileName = file.getOriginalFilename();
        if (fileName == null || !fileName.matches(".*\\.(xlsx|xls)$")) {
            throw new IllegalArgumentException("仅支持 Excel 文件（.xls / .xlsx）");
        }
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new IllegalArgumentException("文件大小不能超过 10MB");
        }
    }

    private ParsedSheet parseSheet(MultipartFile file) {
        try (InputStream inputStream = file.getInputStream();
             Workbook workbook = WorkbookFactory.create(inputStream)) {
            if (workbook.getNumberOfSheets() <= 0) {
                throw new IllegalArgumentException("Excel 中没有可读取的工作表");
            }

            Sheet sheet = workbook.getSheetAt(0);
            DataFormatter formatter = new DataFormatter(Locale.CHINA);
            FormulaEvaluator evaluator = workbook.getCreationHelper().createFormulaEvaluator();

            int headerRowIndex = findHeaderRowIndex(sheet, formatter, evaluator);
            if (headerRowIndex < 0) {
                throw new IllegalArgumentException("未识别到表头，请检查 Excel 首行是否为字段名");
            }

            Row headerRow = sheet.getRow(headerRowIndex);
            Map<Integer, String> headerIndexMap = new LinkedHashMap<>();
            int startColumn = Math.max(headerRow.getFirstCellNum(), 0);
            int endColumn = Math.max(headerRow.getLastCellNum(), 0);
            for (int column = startColumn; column < endColumn; column++) {
                String header = readCellValue(headerRow.getCell(column), formatter, evaluator);
                String normalized = normalize(header);
                if (!normalized.isBlank()) {
                    headerIndexMap.put(column, normalized);
                }
            }

            if (headerIndexMap.isEmpty()) {
                throw new IllegalArgumentException("表头为空，无法导入");
            }

            List<ParsedRow> rows = new ArrayList<>();
            for (int rowIndex = headerRowIndex + 1; rowIndex <= sheet.getLastRowNum(); rowIndex++) {
                Row row = sheet.getRow(rowIndex);
                if (row == null) {
                    continue;
                }
                Map<String, String> values = new LinkedHashMap<>();
                boolean hasValue = false;
                for (Map.Entry<Integer, String> entry : headerIndexMap.entrySet()) {
                    String value = readCellValue(row.getCell(entry.getKey()), formatter, evaluator).trim();
                    if (!value.isBlank()) {
                        values.put(entry.getValue(), value);
                        hasValue = true;
                    }
                }
                if (hasValue) {
                    rows.add(new ParsedRow(rowIndex + 1, values));
                }
            }
            return new ParsedSheet(new LinkedHashSet<>(headerIndexMap.values()), rows);
        } catch (IOException e) {
            throw new IllegalArgumentException("Excel 读取失败: " + e.getMessage(), e);
        }
    }

    private int findHeaderRowIndex(Sheet sheet, DataFormatter formatter, FormulaEvaluator evaluator) {
        for (int rowIndex = sheet.getFirstRowNum(); rowIndex <= sheet.getLastRowNum(); rowIndex++) {
            Row row = sheet.getRow(rowIndex);
            if (row == null) {
                continue;
            }
            int startColumn = Math.max(row.getFirstCellNum(), 0);
            int endColumn = Math.max(row.getLastCellNum(), 0);
            int nonBlankCount = 0;
            for (int column = startColumn; column < endColumn; column++) {
                String value = readCellValue(row.getCell(column), formatter, evaluator);
                if (!value.isBlank()) {
                    nonBlankCount++;
                }
            }
            if (nonBlankCount >= 2) {
                return rowIndex;
            }
        }
        return -1;
    }

    private String readCellValue(Cell cell, DataFormatter formatter, FormulaEvaluator evaluator) {
        if (cell == null) {
            return "";
        }
        return formatter.formatCellValue(cell, evaluator).trim();
    }

    private ImportType resolveImportType(String requestedTypeCode, Set<String> normalizedHeaders) {
        if (requestedTypeCode != null && !requestedTypeCode.isBlank() && !"AUTO".equalsIgnoreCase(requestedTypeCode)) {
            return ImportType.fromCode(requestedTypeCode);
        }

        int bestScore = -1;
        ImportType bestType = null;
        for (ImportType importType : ImportType.values()) {
            int score = importType.detectScore(normalizedHeaders);
            if (score > bestScore) {
                bestScore = score;
                bestType = importType;
            }
        }

        if (bestType == null || bestScore < 3) {
            throw new IllegalArgumentException("无法自动识别 Excel 类型，请手动选择导入类型后重试");
        }
        return bestType;
    }

    private ImportType resolveTemplateType(String requestedTypeCode) {
        if (requestedTypeCode == null || requestedTypeCode.isBlank() || "AUTO".equalsIgnoreCase(requestedTypeCode)) {
            return ImportType.PRODUCT_BASE;
        }
        return ImportType.fromCode(requestedTypeCode);
    }

    private SysImportBatch createBatch(Long shopId, String fileName, ImportType importType) {
        SysImportBatch batch = new SysImportBatch();
        batch.setShopId(shopId);
        batch.setBatchNo("BATCH-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase(Locale.ROOT));
        batch.setFileName(fileName);
        batch.setDataType(importType.code);
        batch.setRowCount(0);
        batch.setSuccessCount(0);
        batch.setFailCount(0);
        batch.setUploadStatus("PROCESSING");
        batchMapper.insert(batch);
        return batch;
    }

    private LocalDate importProductBase(Long shopId, ParsedRow row) {
        String externalProductId = parseExternalProductId(row.getFirst("\u5546\u54c1ID", "\u5546\u54c1\u7f16\u53f7", "\u5b9d\u8d1dID", "Item ID", "item_id"));
        String title = row.getRequired("\u5546\u54c1\u6807\u9898", "\u5b9d\u8d1d\u6807\u9898", "\u5546\u54c1\u540d\u79f0", "\u6807\u9898");

        BizProduct product = getOrCreateProduct(shopId, externalProductId, title);
        product.setExternalProductId(resolveExternalProductId(externalProductId, title));

        product.setTitle(title);
        product.setCategory(row.getFirst("\u5546\u54c1\u7c7b\u76ee", "\u7c7b\u76ee\u540d\u79f0", "\u5546\u54c1\u5206\u7c7b", "\u7c7b\u76ee"));
        product.setCostPrice(nullableMoney(parseAmount(row.getFirst("\u6210\u672c\u4ef7", "\u4f9b\u8d27\u4ef7", "\u91c7\u8d2d\u4ef7"))));
        product.setCurrentPrice(nullableMoney(parseAmount(row.getFirst("\u5f53\u524d\u552e\u4ef7", "\u552e\u4ef7", "\u9500\u552e\u4ef7", "\u4e00\u53e3\u4ef7", "\u5546\u54c1\u4ef7\u683c"))));
        product.setStock(defaultInt(parseInteger(row.getFirst("\u5e93\u5b58", "\u53ef\u552e\u5e93\u5b58", "\u603b\u5e93\u5b58"))));
        String status = row.getFirst("\u5546\u54c1\u72b6\u6001", "\u5b9d\u8d1d\u72b6\u6001", "\u72b6\u6001");
        product.setStatus(status == null || status.isBlank() ? "ON_SALE" : status.trim());
        product.setProfileStatus("COMPLETE");

        if (product.getId() == null) {
            productMapper.insert(product);
        } else {
            productMapper.updateById(product);
        }
        return null;
    }

    private LocalDate importProductDailyMetric(Long shopId, Long batchId, ParsedRow row) {
        LocalDate statDate = parseDate(row.getRequired("\u7edf\u8ba1\u65e5\u671f", "\u65e5\u671f", "\u6570\u636e\u65e5\u671f"));
        String externalProductId = parseExternalProductId(row.getFirst("\u5546\u54c1ID", "\u5546\u54c1\u7f16\u53f7", "\u5b9d\u8d1dID", "Item ID", "item_id"));
        String title = row.getFirst("\u5546\u54c1\u6807\u9898", "\u5b9d\u8d1d\u6807\u9898", "\u5546\u54c1\u540d\u79f0", "\u6807\u9898");
        BizProduct product = getOrCreateProduct(shopId, externalProductId, title);

        LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProductDailyStat::getProductId, product.getId())
                .eq(BizProductDailyStat::getStatDate, statDate)
                .last("LIMIT 1");
        BizProductDailyStat stat = statMapper.selectOne(wrapper);
        if (stat == null) {
            stat = new BizProductDailyStat();
            stat.setShopId(shopId);
            stat.setProductId(product.getId());
            stat.setStatDate(statDate);
        }

        Integer visitorCount = parseInteger(row.getFirst("\u8bbf\u5ba2\u6570", "\u8bbf\u5ba2\u4eba\u6570", "UV", "\u6d4f\u89c8\u8bbf\u5ba2\u6570"));
        Integer payItemQty = parseInteger(row.getFirst("\u652f\u4ed8\u4ef6\u6570", "\u9500\u91cf", "\u652f\u4ed8\u5546\u54c1\u4ef6\u6570"));

        stat.setVisitorCount(defaultInt(visitorCount));
        stat.setAddCartCount(defaultInt(parseInteger(row.getFirst("\u52a0\u8d2d\u4eba\u6570", "\u52a0\u8d2d\u4ef6\u6570", "\u52a0\u8d2d\u6570"))));
        stat.setPayBuyerCount(defaultInt(parseInteger(row.getFirst("\u652f\u4ed8\u4e70\u5bb6\u6570", "\u652f\u4ed8\u4eba\u6570"))));
        stat.setSalesCount(defaultInt(payItemQty));
        stat.setTurnover(defaultMoney(parseAmount(row.getFirst("\u652f\u4ed8\u91d1\u989d", "\u6210\u4ea4\u91d1\u989d", "GMV"))));
        stat.setRefundAmount(defaultMoney(parseAmount(row.getFirst("\u9000\u6b3e\u91d1\u989d", "\u552e\u540e\u9000\u6b3e\u91d1\u989d"))));

        BigDecimal conversionRate = parseRate(row.getFirst("\u652f\u4ed8\u8f6c\u5316\u7387", "\u8f6c\u5316\u7387"));
        if (conversionRate == null || conversionRate.compareTo(BigDecimal.ZERO) <= 0) {
            stat.setConversionRate(calculateConversionRate(defaultInt(payItemQty), defaultInt(visitorCount)));
        } else {
            stat.setConversionRate(conversionRate.setScale(4, RoundingMode.HALF_UP));
        }
        stat.setUploadBatchId(batchId);

        if (stat.getId() == null) {
            statMapper.insert(stat);
        } else {
            statMapper.updateById(stat);
        }
        return statDate;
    }

    private LocalDate importTrafficPromoDaily(Long shopId, Long batchId, ParsedRow row) {
        LocalDate statDate = parseDate(row.getRequired("\u7edf\u8ba1\u65e5\u671f", "\u65e5\u671f", "\u6570\u636e\u65e5\u671f"));
        String externalProductId = parseExternalProductId(row.getFirst("\u5546\u54c1ID", "\u5546\u54c1\u7f16\u53f7", "\u5b9d\u8d1dID", "Item ID", "item_id"));
        String title = row.getFirst("\u5546\u54c1\u6807\u9898", "\u5b9d\u8d1d\u6807\u9898", "\u5546\u54c1\u540d\u79f0", "\u6807\u9898");
        BizProduct product = getOrCreateProduct(shopId, externalProductId, title);

        String trafficSource = row.getRequired("\u6d41\u91cf\u6765\u6e90", "\u6765\u6e90\u6e20\u9053", "\u63a8\u5e7f\u6e20\u9053", "\u6e20\u9053");
        LambdaQueryWrapper<TrafficPromoDaily> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TrafficPromoDaily::getShopId, shopId)
                .eq(TrafficPromoDaily::getStatDate, statDate)
                .eq(TrafficPromoDaily::getTrafficSource, trafficSource)
                .eq(TrafficPromoDaily::getProductId, product.getId());
        wrapper.last("LIMIT 1");

        TrafficPromoDaily traffic = trafficPromoDailyMapper.selectOne(wrapper);
        if (traffic == null) {
            traffic = new TrafficPromoDaily();
            traffic.setShopId(shopId);
            traffic.setProductId(product.getId());
            traffic.setStatDate(statDate);
            traffic.setTrafficSource(trafficSource);
        }

        traffic.setImpressionCount(defaultInt(parseInteger(row.getFirst("\u5c55\u73b0\u91cf", "\u66dd\u5149\u91cf", "\u5c55\u793a\u6b21\u6570"))));
        traffic.setClickCount(defaultInt(parseInteger(row.getFirst("\u70b9\u51fb\u91cf", "\u70b9\u51fb\u6b21\u6570"))));
        traffic.setVisitorCount(defaultInt(parseInteger(row.getFirst("\u8bbf\u5ba2\u6570", "\u70b9\u51fb\u8bbf\u5ba2\u6570", "\u5f15\u5bfc\u8bbf\u5ba2\u6570"))));
        traffic.setCostAmount(defaultMoney(parseAmount(row.getFirst("\u82b1\u8d39", "\u6d88\u8017", "\u63a8\u5e7f\u82b1\u8d39"))));
        traffic.setPayAmount(defaultMoney(parseAmount(row.getFirst("\u652f\u4ed8\u91d1\u989d", "\u6210\u4ea4\u91d1\u989d", "\u5f15\u5bfc\u652f\u4ed8\u91d1\u989d"))));

        BigDecimal roi = parseRate(row.getFirst("ROI", "ROAS"));
        traffic.setRoi(roi == null ? BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP) : roi.setScale(4, RoundingMode.HALF_UP));
        traffic.setUploadBatchId(batchId);

        if (traffic.getId() == null) {
            trafficPromoDailyMapper.insert(traffic);
        } else {
            trafficPromoDailyMapper.updateById(traffic);
        }
        return statDate;
    }

    private BizProduct getOrCreateProduct(Long shopId, String externalProductId, String title) {
        BizProduct product = findProduct(shopId, externalProductId, title);
        boolean changed = false;
        if (product == null) {
            product = new BizProduct();
            product.setShopId(shopId);
            product.setExternalProductId(resolveExternalProductId(externalProductId, title));
            product.setTitle(trimToNull(title));
            product.setStock(0);
            product.setStatus("UNKNOWN");
            product.setProfileStatus("PLACEHOLDER");
            productMapper.insert(product);
            return product;
        }

        if (externalProductId != null
                && !externalProductId.isBlank()
                && (product.getExternalProductId() == null
                || product.getExternalProductId().isBlank()
                || product.getExternalProductId().startsWith("PLACEHOLDER-"))) {
            product.setExternalProductId(externalProductId);
            changed = true;
        }
        if ((product.getTitle() == null || product.getTitle().isBlank()) && title != null && !title.isBlank()) {
            product.setTitle(title.trim());
            changed = true;
        }
        if (product.getStatus() == null || product.getStatus().isBlank()) {
            product.setStatus("UNKNOWN");
            changed = true;
        }
        if (product.getProfileStatus() == null || product.getProfileStatus().isBlank()) {
            product.setProfileStatus("PLACEHOLDER");
            changed = true;
        }
        if (changed) {
            productMapper.updateById(product);
        }
        return product;
    }

    private BizProduct findProduct(Long shopId, String externalProductId, String title) {
        if (externalProductId != null && !externalProductId.isBlank()) {
            LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(BizProduct::getShopId, shopId)
                    .eq(BizProduct::getExternalProductId, externalProductId)
                    .last("LIMIT 1");
            BizProduct product = productMapper.selectOne(wrapper);
            if (product != null) {
                return product;
            }
        }

        if (title != null && !title.isBlank()) {
            LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(BizProduct::getShopId, shopId)
                    .eq(BizProduct::getTitle, title.trim())
                    .last("LIMIT 1");
            return productMapper.selectOne(wrapper);
        }
        return null;
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

    private String buildSummary(ImportType importType, int successCount, int failCount, boolean autoDetected) {
        StringBuilder builder = new StringBuilder();
        builder.append("已按“").append(importType.label).append("”处理，成功 ")
                .append(successCount).append(" 行，失败 ").append(failCount).append(" 行");
        if (autoDetected) {
            builder.append("，导入类型由表头自动识别");
        }
        return builder.toString();
    }

    private String normalize(String value) {
        return ParsedRow.normalizeStatic(value);
    }

    private String parseExternalProductId(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalized = value.replace(",", "").trim();
        if (normalized.endsWith(".0")) {
            normalized = normalized.substring(0, normalized.length() - 2);
        }
        try {
            if (normalized.matches("[+-]?\\d+(\\.\\d+)?([eE][+-]?\\d+)?")) {
                return new BigDecimal(normalized).stripTrailingZeros().toPlainString();
            }
            return normalized;
        } catch (Exception e) {
            return normalized;
        }
    }

    private String resolveExternalProductId(String externalProductId, String title) {
        if (externalProductId != null && !externalProductId.isBlank()) {
            return externalProductId.trim();
        }
        if (title != null && !title.isBlank()) {
            return "PLACEHOLDER-" + Math.abs((title.trim() + "-" + System.nanoTime()).hashCode());
        }
        return "PLACEHOLDER-" + System.currentTimeMillis();
    }

    private Integer parseInteger(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            String normalized = value.replace(",", "").trim();
            return new BigDecimal(normalized).setScale(0, RoundingMode.HALF_UP).intValue();
        } catch (Exception e) {
            return null;
        }
    }

    private BigDecimal parseAmount(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            String normalized = value.replace("￥", "")
                    .replace("¥", "")
                    .replace("元", "")
                    .replace(",", "")
                    .trim();
            return new BigDecimal(normalized).setScale(2, RoundingMode.HALF_UP);
        } catch (Exception e) {
            return null;
        }
    }

    private BigDecimal parseRate(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            String normalized = value.replace("%", "").trim();
            BigDecimal numeric = new BigDecimal(normalized);
            if (value.contains("%") || numeric.compareTo(BigDecimal.ONE) > 0) {
                return numeric.divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_UP);
            }
            return numeric.setScale(4, RoundingMode.HALF_UP);
        } catch (Exception e) {
            return null;
        }
    }

    private LocalDate parseDate(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("缺少日期字段");
        }

        String raw = value.trim();
        String normalized = raw.length() > 10 ? raw.substring(0, 10) : raw;

        List<DateTimeFormatter> formatters = List.of(
                DateTimeFormatter.ofPattern("yyyy-MM-dd"),
                DateTimeFormatter.ofPattern("yyyy/M/d"),
                DateTimeFormatter.ofPattern("yyyy/MM/dd"),
                DateTimeFormatter.ofPattern("yyyy.MM.dd"),
                DateTimeFormatter.ofPattern("yyyyMMdd")
        );
        for (DateTimeFormatter formatter : formatters) {
            try {
                return LocalDate.parse(normalized, formatter);
            } catch (DateTimeParseException ignore) {
            }
        }

        String replaced = normalized.replace("/", "-").replace(".", "-");
        try {
            return LocalDate.parse(replaced, DateTimeFormatter.ofPattern("yyyy-MM-dd"));
        } catch (DateTimeParseException ignore) {
        }

        if (raw.matches("\\d+(\\.\\d+)?")) {
            BigDecimal excelDate = new BigDecimal(raw);
            int days = excelDate.setScale(0, RoundingMode.DOWN).intValue();
            if (days > 20000) {
                return LocalDate.of(1899, 12, 30).plusDays(days);
            }
        }

        try {
            return LocalDateTime.parse(raw, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")).toLocalDate();
        } catch (DateTimeParseException ignore) {
        }

        throw new IllegalArgumentException("无法解析日期: " + value);
    }

    private Integer defaultInt(Integer value) {
        return value == null ? 0 : value;
    }

    private BigDecimal defaultMoney(BigDecimal value) {
        if (value == null) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal nullableMoney(BigDecimal value) {
        return value == null ? null : value.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal calculateConversionRate(int salesCount, int visitorCount) {
        if (salesCount <= 0 || visitorCount <= 0) {
            return BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP);
        }
        return BigDecimal.valueOf(salesCount)
                .divide(BigDecimal.valueOf(visitorCount), 4, RoundingMode.HALF_UP);
    }

    private String trimToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private record ParsedSheet(Set<String> headers, List<ParsedRow> rows) {
    }

    private record ParsedRow(int rowNumber, Map<String, String> values) {
        String getFirst(String... aliases) {
            for (String alias : aliases) {
                String value = values.get(normalizeStatic(alias));
                if (value != null && !value.isBlank()) {
                    return value.trim();
                }
            }
            return null;
        }

        String getRequired(String... aliases) {
            String value = getFirst(aliases);
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException("缺少字段: " + aliases[0]);
            }
            return value;
        }

        private static String normalizeStatic(String value) {
            if (value == null) {
                return "";
            }
            return value.trim()
                    .toLowerCase(Locale.ROOT)
                    .replace("（", "(")
                    .replace("）", ")")
                    .replace("：", "")
                    .replace(":", "")
                    .replace(" ", "")
                    .replace("　", "")
                    .replace("_", "")
                    .replace("-", "")
                    .replace("/", "")
                    .replace("\\", "");
        }
    }

    private enum ImportType {
        PRODUCT_BASE(
                "PRODUCT_BASE",
                "商品基础信息",
                "product",
                "商品基础信息导入模板.xlsx",
                "商品基础信息",
                List.of("商品ID", "商品标题", "商品类目", "成本价", "当前售价", "库存", "商品状态"),
                List.of(
                        List.<Object>of("202603260001", "防晒衣女夏季薄款", "女装/外套", "59.00", "99.00", "180", "ON_SALE")
                ),
                List.of(
                        List.of("商品ID", "商品编号", "宝贝ID", "Item ID"),
                        List.of("商品标题", "宝贝标题", "商品名称", "标题"),
                        List.of("当前售价", "售价", "销售价", "一口价", "商品价格"),
                        List.of("库存", "可售库存", "总库存")
                )
        ),
        PRODUCT_DAILY_METRIC(
                "PRODUCT_DAILY_METRIC",
                "商品经营日报",
                "product_daily_metric",
                "商品经营日报导入模板.xlsx",
                "商品经营日报",
                List.of("统计日期", "商品ID", "商品标题", "访客数", "加购人数", "支付买家数", "支付件数", "支付金额", "退款金额", "支付转化率"),
                List.of(
                        List.<Object>of("2026-03-26", "202603260001", "防晒衣女夏季薄款", "860", "72", "38", "45", "4455.00", "120.00", "5.23%")
                ),
                List.of(
                        List.of("统计日期", "日期", "数据日期"),
                        List.of("商品ID", "商品编号", "宝贝ID", "Item ID"),
                        List.of("访客数", "访客人数", "UV", "浏览访客数"),
                        List.of("支付件数", "销量", "支付商品件数"),
                        List.of("支付金额", "成交金额", "GMV")
                )
        ),
        TRAFFIC_PROMO_DAILY(
                "TRAFFIC_PROMO_DAILY",
                "流量推广日报",
                "traffic_promo_daily",
                "流量推广日报导入模板.xlsx",
                "流量推广日报",
                List.of("统计日期", "商品ID", "商品标题", "流量来源", "展现量", "点击量", "访客数", "花费", "支付金额", "ROI"),
                List.of(
                        List.<Object>of("2026-03-26", "202603260001", "防晒衣女夏季薄款", "直通车", "15600", "680", "520", "388.00", "4200.00", "10.82")
                ),
                List.of(
                        List.of("统计日期", "日期", "数据日期"),
                        List.of("流量来源", "来源渠道", "推广渠道", "渠道"),
                        List.of("展现量", "曝光量", "展示次数"),
                        List.of("点击量", "点击次数"),
                        List.of("花费", "消耗", "推广花费")
                )
        );

        private final String code;
        private final String label;
        private final String targetTable;
        private final String templateFileName;
        private final String sheetName;
        private final List<String> templateHeaders;
        private final List<List<Object>> sampleRows;
        private final List<List<String>> detectGroups;

        ImportType(
                String code,
                String label,
                String targetTable,
                String templateFileName,
                String sheetName,
                List<String> templateHeaders,
                List<List<Object>> sampleRows,
                List<List<String>> detectGroups
        ) {
            this.code = code;
            this.label = label;
            this.targetTable = targetTable;
            this.templateFileName = templateFileName;
            this.sheetName = sheetName;
            this.templateHeaders = templateHeaders;
            this.sampleRows = sampleRows;
            this.detectGroups = detectGroups;
        }

        static ImportType fromCode(String code) {
            for (ImportType value : values()) {
                if (value.code.equalsIgnoreCase(code)) {
                    return value;
                }
            }
            throw new IllegalArgumentException("不支持的导入类型: " + code);
        }

        int detectScore(Set<String> headers) {
            int score = 0;
            for (List<String> group : detectGroups) {
                boolean matched = group.stream()
                        .map(ParsedRow::normalizeStatic)
                        .anyMatch(headers::contains);
                if (matched) {
                    score++;
                }
            }
            return score;
        }

        List<List<String>> templateHead() {
            return templateHeaders.stream().map(List::of).toList();
        }

        List<List<Object>> templateRows() {
            return sampleRows;
        }
    }
}
