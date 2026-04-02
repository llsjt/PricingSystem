package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.example.pricing.dto.MockExcelExportDTO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * 生成模拟电商平台导出文件，供前端页面直接下载。
 */
@Slf4j
@Service
public class MockExcelExportService {

    private static final ZoneId ZONE_ID = ZoneId.of("Asia/Shanghai");
    private static final int MAX_PRODUCT_COUNT = 5000;
    private static final int MAX_DETAIL_ROW_COUNT = 20000;
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE;

    private static final List<String> PRODUCT_HEADERS = List.of("商品ID", "商品标题", "商品类目", "成本价", "当前售价", "库存", "商品状态");
    private static final List<String> DAILY_HEADERS = List.of(
            "统计日期", "商品ID", "商品标题", "访客数", "加购人数", "支付买家数", "支付件数", "支付金额", "退款金额", "支付转化率"
    );
    private static final List<String> SKU_HEADERS = List.of(
            "商品ID", "商品标题", "SKU ID", "SKU名称", "SKU属性", "SKU售价", "SKU成本价", "SKU库存"
    );
    private static final List<String> TRAFFIC_HEADERS = List.of(
            "统计日期", "商品ID", "商品标题", "流量来源", "展现量", "点击量", "访客数", "花费", "支付金额", "ROI"
    );

    private static final String[] TITLE_PREFIXES = {"2026新款", "爆款升级", "高颜值", "轻奢质感", "旗舰款", "热卖同款"};
    private static final String[] TITLE_SUFFIXES = {"", " 女款", " 男款", " 家用", " 旅行装", " 礼盒装"};
    private static final String[] TRAFFIC_SOURCES = {"直通车", "万相台", "手淘搜索", "猜你喜欢", "活动会场", "短视频", "直播间"};
    private static final String[] COLORS = {"雅黑", "云白", "雾蓝", "奶杏", "石墨灰", "抹茶绿", "樱花粉"};
    private static final String[] SIZES = {"S", "M", "L", "XL", "2XL"};
    private static final String[] VERSIONS = {"标准版", "升级版", "高配版", "轻享版"};

    private static final List<CategoryTopic> CATEGORY_TOPICS = List.of(
            new CategoryTopic("女装/外套", List.of("轻薄防晒衣", "短款针织开衫", "宽松牛仔外套")),
            new CategoryTopic("男装/T恤", List.of("速干运动T恤", "纯棉圆领短袖", "商务休闲Polo")),
            new CategoryTopic("鞋靴/休闲鞋", List.of("透气跑步鞋", "厚底小白鞋", "轻量徒步鞋")),
            new CategoryTopic("家居/收纳", List.of("可折叠收纳箱", "分格收纳盒", "抽屉整理篮")),
            new CategoryTopic("食品/零食", List.of("低糖坚果礼盒", "冻干水果脆", "手作曲奇礼袋")),
            new CategoryTopic("数码/配件", List.of("磁吸快充数据线", "降噪蓝牙耳机", "折叠手机支架")),
            new CategoryTopic("美妆/护肤", List.of("清润补水面膜", "控油洁面乳", "修护精华喷雾")),
            new CategoryTopic("母婴/用品", List.of("透气婴儿睡袋", "硅胶辅食分格盘", "宝宝云柔浴巾")),
            new CategoryTopic("宠物/用品", List.of("豆腐猫砂", "宠物冻干零食", "防滑宠物食盆")),
            new CategoryTopic("运动/户外", List.of("户外速开帐篷", "瑜伽弹力带", "保温运动水壶"))
    );

    public void downloadBundle(MockExcelExportDTO dto, HttpServletResponse response) {
        MockExcelExportDTO options = normalizeOptions(dto);
        Random random = new Random(options.getSeed());
        List<ProductSpec> products = buildProducts(options.getProductCount(), options.getStartProductId(), random);

        List<WorkbookPayload> payloads = List.of(
                new WorkbookPayload("product_base_mock.xlsx", "商品基础信息", PRODUCT_HEADERS, buildProductRows(products)),
                new WorkbookPayload(
                        "product_daily_metric_mock.xlsx",
                        "商品经营日报",
                        DAILY_HEADERS,
                        buildDailyRows(products, options.getDailyCount(), options.getStartDate(), random)
                ),
                new WorkbookPayload("product_sku_mock.xlsx", "商品SKU", SKU_HEADERS, buildSkuRows(products, options.getSkuCount(), random)),
                new WorkbookPayload(
                        "traffic_promo_daily_mock.xlsx",
                        "流量推广日报",
                        TRAFFIC_HEADERS,
                        buildTrafficRows(products, options.getTrafficCount(), options.getStartDate(), random)
                )
        );

        String bundleName = "mock_excel_bundle_" + System.currentTimeMillis() + ".zip";

        try {
            response.setContentType("application/zip");
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.setHeader(
                    "Content-disposition",
                    "attachment;filename*=utf-8''" + URLEncoder.encode(bundleName, StandardCharsets.UTF_8).replaceAll("\\+", "%20")
            );

            try (ZipOutputStream zipOutputStream = new ZipOutputStream(response.getOutputStream(), StandardCharsets.UTF_8)) {
                for (WorkbookPayload payload : payloads) {
                    zipOutputStream.putNextEntry(new ZipEntry(payload.fileName()));
                    zipOutputStream.write(buildWorkbook(payload.sheetName(), payload.headers(), payload.rows()));
                    zipOutputStream.closeEntry();
                }
                zipOutputStream.finish();
            }
        } catch (IOException e) {
            log.error("Download mock excel bundle failed", e);
            throw new RuntimeException("下载模拟 Excel 失败");
        }
    }

    private MockExcelExportDTO normalizeOptions(MockExcelExportDTO input) {
        MockExcelExportDTO dto = input == null ? new MockExcelExportDTO() : input;

        int productCount = requireCount("商品基础信息条数", dto.getProductCount(), 1, MAX_PRODUCT_COUNT);
        int dailyCount = requireCount("商品日指标条数", dto.getDailyCount(), productCount, MAX_DETAIL_ROW_COUNT);
        int skuCount = requireCount("商品 SKU 条数", dto.getSkuCount(), productCount, MAX_DETAIL_ROW_COUNT);
        int trafficCount = requireCount("流量推广条数", dto.getTrafficCount(), productCount, MAX_DETAIL_ROW_COUNT);

        long startProductId = dto.getStartProductId() == null || dto.getStartProductId() <= 0
                ? defaultStartProductId()
                : dto.getStartProductId();
        LocalDate startDate = dto.getStartDate() == null ? LocalDate.now(ZONE_ID) : dto.getStartDate();
        long seed = dto.getSeed() == null ? 20260402L : dto.getSeed();

        MockExcelExportDTO normalized = new MockExcelExportDTO();
        normalized.setProductCount(productCount);
        normalized.setDailyCount(dailyCount);
        normalized.setSkuCount(skuCount);
        normalized.setTrafficCount(trafficCount);
        normalized.setStartProductId(startProductId);
        normalized.setStartDate(startDate);
        normalized.setSeed(seed);
        return normalized;
    }

    private int requireCount(String label, Integer value, int minValue, int maxValue) {
        if (value == null) {
            throw new IllegalArgumentException(label + "不能为空");
        }
        if (value < minValue) {
            if (minValue > 1) {
                throw new IllegalArgumentException(label + "不能小于商品基础信息条数");
            }
            throw new IllegalArgumentException(label + "必须大于 0");
        }
        if (value > maxValue) {
            throw new IllegalArgumentException(label + "不能超过 " + maxValue);
        }
        return value;
    }

    private long defaultStartProductId() {
        String prefix = LocalDate.now(ZONE_ID).format(DateTimeFormatter.BASIC_ISO_DATE);
        return Long.parseLong(prefix) * 10000L + 1;
    }

    private List<ProductSpec> buildProducts(int productCount, long startProductId, Random random) {
        List<ProductSpec> products = new ArrayList<>();
        for (int index = 0; index < productCount; index++) {
            CategoryTopic categoryTopic = CATEGORY_TOPICS.get(index % CATEGORY_TOPICS.size());
            String topic = categoryTopic.topics().get(random.nextInt(categoryTopic.topics().size()));
            String prefix = TITLE_PREFIXES[(index + random.nextInt(TITLE_PREFIXES.length)) % TITLE_PREFIXES.length];
            String suffix = TITLE_SUFFIXES[(index + random.nextInt(TITLE_SUFFIXES.length)) % TITLE_SUFFIXES.length];
            String title = (prefix + topic + suffix + " " + String.format("%03d", index + 1)).trim();

            BigDecimal costPrice = money(decimal(random, 12, 220));
            BigDecimal salePrice = money(costPrice.multiply(decimal(random, 1.2, 2.1)));
            if (salePrice.compareTo(costPrice) <= 0) {
                salePrice = money(costPrice.multiply(BigDecimal.valueOf(1.2)));
            }

            int stock = 60 + random.nextInt(1141);
            String status = random.nextDouble() < 0.9 ? "ON_SALE" : "OFF_SHELF";
            double popularity = 0.8 + random.nextDouble() * 0.8;

            products.add(new ProductSpec(
                    String.valueOf(startProductId + index),
                    title,
                    categoryTopic.category(),
                    costPrice,
                    salePrice,
                    stock,
                    status,
                    popularity
            ));
        }
        return products;
    }

    private List<List<Object>> buildProductRows(List<ProductSpec> products) {
        List<List<Object>> rows = new ArrayList<>();
        for (ProductSpec product : products) {
            rows.add(List.of(
                    product.productId(),
                    product.title(),
                    product.category(),
                    decimalText(product.costPrice()),
                    decimalText(product.salePrice()),
                    product.stock(),
                    product.status()
            ));
        }
        return rows;
    }

    private List<List<Object>> buildDailyRows(List<ProductSpec> products, int totalRows, LocalDate newestDate, Random random) {
        int[] counts = allocateCounts(totalRows, products.size(), random);
        List<List<Object>> rows = new ArrayList<>();

        for (int index = 0; index < products.size(); index++) {
            ProductSpec product = products.get(index);
            for (int dayOffset = 0; dayOffset < counts[index]; dayOffset++) {
                LocalDate statDate = newestDate.minusDays(dayOffset);
                int visitorCount = Math.max(80, (int) (randomRange(random, 120, 1600) * product.popularity()));
                int addCartCount = clamp((int) (visitorCount * randomRange(random, 0.05, 0.18)), 5, visitorCount);
                int payBuyerCount = clamp((int) (addCartCount * randomRange(random, 0.45, 0.85)), 1, addCartCount);
                int salesCount = Math.max(payBuyerCount, (int) (payBuyerCount * randomRange(random, 1.0, 1.3)));
                BigDecimal turnover = money(
                        product.salePrice()
                                .multiply(BigDecimal.valueOf(salesCount))
                                .multiply(decimal(random, 0.96, 1.04))
                );
                BigDecimal refundAmount = money(turnover.multiply(decimal(random, 0.0, 0.08)));
                BigDecimal conversionRate = BigDecimal.valueOf(salesCount)
                        .divide(BigDecimal.valueOf(visitorCount), 4, RoundingMode.HALF_UP);

                rows.add(List.of(
                        statDate.format(DATE_FORMATTER),
                        product.productId(),
                        product.title(),
                        visitorCount,
                        addCartCount,
                        payBuyerCount,
                        salesCount,
                        decimalText(turnover),
                        decimalText(refundAmount),
                        percentText(conversionRate)
                ));
            }
        }

        rows.sort((left, right) -> {
            int dateCompare = String.valueOf(right.get(0)).compareTo(String.valueOf(left.get(0)));
            if (dateCompare != 0) {
                return dateCompare;
            }
            return String.valueOf(right.get(1)).compareTo(String.valueOf(left.get(1)));
        });
        return rows;
    }

    private List<List<Object>> buildSkuRows(List<ProductSpec> products, int totalRows, Random random) {
        int[] counts = allocateCounts(totalRows, products.size(), random);
        List<List<Object>> rows = new ArrayList<>();

        for (int index = 0; index < products.size(); index++) {
            ProductSpec product = products.get(index);
            int rowCount = counts[index];
            int baseStock = Math.max(1, product.stock() / rowCount);
            for (int variantIndex = 0; variantIndex < rowCount; variantIndex++) {
                String color = COLORS[variantIndex % COLORS.length];
                String size = SIZES[(variantIndex / COLORS.length) % SIZES.length];
                String version = VERSIONS[(variantIndex / (COLORS.length * SIZES.length)) % VERSIONS.length];
                String skuId = product.productId() + "-" + String.format("%03d", variantIndex + 1);
                String skuAttr = "颜色:" + color + ";尺码:" + size + ";版本:" + version;
                String skuName = product.title() + " - " + color + size + " " + version;

                BigDecimal salePrice = money(product.salePrice().multiply(decimal(random, 0.92, 1.08)));
                BigDecimal floorPrice = money(product.costPrice().multiply(BigDecimal.valueOf(1.05)));
                if (salePrice.compareTo(floorPrice) < 0) {
                    salePrice = floorPrice;
                }

                BigDecimal costPrice = money(product.costPrice().multiply(decimal(random, 0.96, 1.04)));
                if (costPrice.compareTo(salePrice) >= 0) {
                    costPrice = money(salePrice.multiply(BigDecimal.valueOf(0.84)));
                }

                int stock = Math.max(3, (int) (baseStock * randomRange(random, 0.7, 1.4)));

                rows.add(List.of(
                        product.productId(),
                        product.title(),
                        skuId,
                        skuName,
                        skuAttr,
                        decimalText(salePrice),
                        decimalText(costPrice),
                        stock
                ));
            }
        }

        rows.sort((left, right) -> {
            int productCompare = String.valueOf(left.get(0)).compareTo(String.valueOf(right.get(0)));
            if (productCompare != 0) {
                return productCompare;
            }
            return String.valueOf(left.get(2)).compareTo(String.valueOf(right.get(2)));
        });
        return rows;
    }

    private List<List<Object>> buildTrafficRows(List<ProductSpec> products, int totalRows, LocalDate newestDate, Random random) {
        int[] counts = allocateCounts(totalRows, products.size(), random);
        List<List<Object>> rows = new ArrayList<>();

        for (int index = 0; index < products.size(); index++) {
            ProductSpec product = products.get(index);
            for (int offset = 0; offset < counts[index]; offset++) {
                String trafficSource = TRAFFIC_SOURCES[offset % TRAFFIC_SOURCES.length];
                LocalDate statDate = newestDate.minusDays(offset / TRAFFIC_SOURCES.length);
                BigDecimal ctr = decimal(random, 0.02, 0.09);
                int impressionCount = Math.max(400, (int) (randomRange(random, 1800, 20000) * product.popularity()));
                int clickCount = Math.max(20, BigDecimal.valueOf(impressionCount).multiply(ctr).intValue());
                int visitorCount = clamp((int) (clickCount * randomRange(random, 0.60, 0.92)), 10, clickCount);
                int paidOrders = Math.max(1, (int) (visitorCount * randomRange(random, 0.01, 0.08)));
                BigDecimal payAmount = money(
                        product.salePrice()
                                .multiply(BigDecimal.valueOf(paidOrders))
                                .multiply(decimal(random, 0.95, 1.08))
                );

                BigDecimal roiRate = decimal(random, 0.05, 0.20).setScale(4, RoundingMode.HALF_UP);
                BigDecimal costAmount = money(payAmount.divide(roiRate.multiply(BigDecimal.valueOf(100)), 6, RoundingMode.HALF_UP));

                rows.add(List.of(
                        statDate.format(DATE_FORMATTER),
                        product.productId(),
                        product.title(),
                        trafficSource,
                        impressionCount,
                        clickCount,
                        visitorCount,
                        decimalText(costAmount),
                        decimalText(payAmount),
                        percentText(roiRate)
                ));
            }
        }

        rows.sort((left, right) -> {
            int dateCompare = String.valueOf(right.get(0)).compareTo(String.valueOf(left.get(0)));
            if (dateCompare != 0) {
                return dateCompare;
            }
            int productCompare = String.valueOf(right.get(1)).compareTo(String.valueOf(left.get(1)));
            if (productCompare != 0) {
                return productCompare;
            }
            return String.valueOf(right.get(3)).compareTo(String.valueOf(left.get(3)));
        });
        return rows;
    }

    private byte[] buildWorkbook(String sheetName, List<String> headers, List<List<Object>> rows) throws IOException {
        try (ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {
            EasyExcel.write(outputStream)
                    .autoCloseStream(false)
                    .head(singleRowHead(headers))
                    .sheet(sheetName)
                    .doWrite(rows);
            return outputStream.toByteArray();
        }
    }

    private List<List<String>> singleRowHead(List<String> headers) {
        List<List<String>> head = new ArrayList<>();
        for (String header : headers) {
            head.add(List.of(header));
        }
        return head;
    }

    private int[] allocateCounts(int totalRows, int bucketCount, Random random) {
        int[] counts = new int[bucketCount];
        Arrays.fill(counts, 1);
        for (int remaining = totalRows - bucketCount; remaining > 0; remaining--) {
            counts[random.nextInt(bucketCount)]++;
        }
        return counts;
    }

    private BigDecimal decimal(Random random, double min, double max) {
        return BigDecimal.valueOf(randomRange(random, min, max));
    }

    private double randomRange(Random random, double min, double max) {
        return min + (max - min) * random.nextDouble();
    }

    private BigDecimal money(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private String decimalText(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP).toPlainString();
    }

    private String percentText(BigDecimal rate) {
        return rate.multiply(BigDecimal.valueOf(100))
                .setScale(2, RoundingMode.HALF_UP)
                .toPlainString() + "%";
    }

    private int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(value, max));
    }

    private record CategoryTopic(String category, List<String> topics) {
    }

    private record ProductSpec(
            String productId,
            String title,
            String category,
            BigDecimal costPrice,
            BigDecimal salePrice,
            int stock,
            String status,
            double popularity
    ) {
    }

    private record WorkbookPayload(String fileName, String sheetName, List<String> headers, List<List<Object>> rows) {
    }
}
