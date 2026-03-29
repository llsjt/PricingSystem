package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.vo.DecisionComparisonVO;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.DecisionTaskItemVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class DecisionTaskServiceImpl implements DecisionTaskService {

    private final PricingTaskMapper taskMapper;
    private final PricingResultMapper resultMapper;
    private final AgentRunLogMapper logMapper;
    private final ProductMapper productMapper;

    @Value("${agent.python.base-url:http://localhost:8000}")
    private String pythonBaseUrl;

    @Value("${agent.python.dispatch-path:/internal/tasks/dispatch}")
    private String pythonDispatchPath;

    @Value("${agent.python.internal-token:}")
    private String pythonInternalToken;

    @Override
    public Long startTask(List<Long> productIds, String strategyGoal, String constraints) {
        if (productIds == null || productIds.isEmpty()) {
            throw new IllegalArgumentException("至少选择一个商品");
        }

        Long productId = productIds.get(0);
        Product product = productMapper.selectById(productId);
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }

        PricingTask task = new PricingTask();
        task.setTaskCode("TASK-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase());
        task.setShopId(product.getShopId());
        task.setProductId(product.getId());
        task.setCurrentPrice(scaleMoney(product.getCurrentPrice()));
        task.setBaselineProfit(BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP));
        task.setTaskStatus("PENDING");
        taskMapper.insert(task);

        try {
            dispatchToPython(task.getId(), productId, productIds, strategyGoal, constraints);
            task.setTaskStatus("RUNNING");
            taskMapper.updateById(task);
        } catch (Exception e) {
            log.error("Dispatch decision task to python failed, taskId={}", task.getId(), e);
            task.setTaskStatus("FAILED");
            taskMapper.updateById(task);
            throw new IllegalStateException("任务派发到 Python 协作后端失败: " + e.getMessage(), e);
        }

        return task.getId();
    }

    @Override
    public List<DecisionComparisonVO> getTaskResult(Long taskId) {
        return buildComparisonRows(taskId);
    }

    @Override
    public List<DecisionLogVO> getTaskLogs(Long taskId) {
        LambdaQueryWrapper<AgentRunLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentRunLog::getTaskId, taskId).orderByAsc(AgentRunLog::getRunOrder, AgentRunLog::getId);
        return logMapper.selectList(wrapper).stream().map(logItem -> {
            DecisionLogVO vo = new DecisionLogVO();
            vo.setId(logItem.getId());
            vo.setAgentCode(logItem.getAgentCode());
            vo.setAgentName(logItem.getAgentName());
            vo.setRunOrder(logItem.getRunOrder());
            vo.setRunStatus(logItem.getRunStatus());
            vo.setOutputSummary(logItem.getOutputSummary());
            vo.setSuggestedPrice(logItem.getSuggestedPrice());
            vo.setPredictedProfit(logItem.getPredictedProfit());
            vo.setConfidenceScore(logItem.getConfidenceScore());
            vo.setRiskLevel(logItem.getRiskLevel());
            vo.setNeedManualReview(logItem.getNeedManualReview() != null && logItem.getNeedManualReview() == 1);
            vo.setCreatedAt(logItem.getCreatedAt());
            return vo;
        }).toList();
    }

    @Override
    public String getTaskStatus(Long taskId) {
        PricingTask task = taskMapper.selectById(taskId);
        if (task == null || task.getTaskStatus() == null || task.getTaskStatus().isBlank()) {
            return "NOT_FOUND";
        }
        return task.getTaskStatus().trim();
    }

    @Override
    public Page<DecisionTaskItemVO> getTasks(int page, int size, String status, String startTime, String endTime, String sortOrder) {
        Page<PricingTask> pageParam = new Page<>(Math.max(page, 1), size <= 0 ? 10 : size);
        LambdaQueryWrapper<PricingTask> wrapper = new LambdaQueryWrapper<>();
        if (status != null && !status.isBlank()) {
            wrapper.eq(PricingTask::getTaskStatus, status);
        }

        LocalDateTime start = parseDateTime(startTime, false);
        LocalDateTime end = parseDateTime(endTime, true);
        if (start != null) {
            wrapper.ge(PricingTask::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(PricingTask::getCreatedAt, end);
        }

        if ("asc".equalsIgnoreCase(sortOrder)) {
            wrapper.orderByAsc(PricingTask::getCreatedAt, PricingTask::getId);
        } else {
            wrapper.orderByDesc(PricingTask::getCreatedAt, PricingTask::getId);
        }

        Page<PricingTask> taskPage = taskMapper.selectPage(pageParam, wrapper);
        Page<DecisionTaskItemVO> resultPage = new Page<>();
        resultPage.setCurrent(taskPage.getCurrent());
        resultPage.setSize(taskPage.getSize());
        resultPage.setTotal(taskPage.getTotal());
        resultPage.setRecords(taskPage.getRecords().stream().map(this::toTaskItem).toList());
        return resultPage;
    }

    @Override
    public Map<String, Long> getTaskStats(String startTime, String endTime) {
        LambdaQueryWrapper<PricingTask> wrapper = new LambdaQueryWrapper<>();
        LocalDateTime start = parseDateTime(startTime, false);
        LocalDateTime end = parseDateTime(endTime, true);
        if (start != null) {
            wrapper.ge(PricingTask::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(PricingTask::getCreatedAt, end);
        }

        List<PricingTask> tasks = taskMapper.selectList(wrapper);
        long total = tasks.size();
        long completed = tasks.stream().filter(task -> "COMPLETED".equalsIgnoreCase(task.getTaskStatus())).count();
        long running = tasks.stream().filter(task -> "RUNNING".equalsIgnoreCase(task.getTaskStatus())).count();
        long failed = tasks.stream().filter(task -> "FAILED".equalsIgnoreCase(task.getTaskStatus())).count();
        return Map.of("total", total, "completed", completed, "running", running, "failed", failed);
    }

    @Override
    public List<DecisionComparisonVO> getTaskComparison(Long taskId) {
        return buildComparisonRows(taskId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void applyDecision(Long resultId) {
        PricingResult result = resultMapper.selectById(resultId);
        if (result == null) {
            throw new IllegalArgumentException("结果不存在");
        }
        PricingTask task = taskMapper.selectById(result.getTaskId());
        if (task == null) {
            throw new IllegalArgumentException("任务不存在");
        }
        Product product = productMapper.selectById(task.getProductId());
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }
        product.setCurrentPrice(scaleMoney(result.getFinalPrice()));
        productMapper.updateById(product);
    }

    @Override
    public void exportDecisionReport(Long taskId, HttpServletResponse response) throws IOException {
        List<DecisionComparisonVO> rows = buildComparisonRows(taskId);
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("DecisionReport_" + taskId, "UTF-8").replaceAll("\\+", "%20");
        response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName + ".xlsx");
        EasyExcel.write(response.getOutputStream(), DecisionComparisonVO.class).sheet("决策报告").doWrite(rows);
    }

    private void dispatchToPython(Long taskId, Long productId, List<Long> productIds, String strategyGoal, String constraints) {
        String url = UriComponentsBuilder.fromHttpUrl(pythonBaseUrl)
                .path(pythonDispatchPath)
                .toUriString();

        Map<String, Object> payload = new HashMap<>();
        payload.put("taskId", taskId);
        payload.put("productId", productId);
        payload.put("productIds", productIds);
        payload.put("strategyGoal", strategyGoal);
        payload.put("constraints", constraints);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (pythonInternalToken != null && !pythonInternalToken.isBlank()) {
            headers.set("X-Internal-Token", pythonInternalToken);
        }

        RestTemplate restTemplate = new RestTemplate();
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);
        ResponseEntity<Map> response = restTemplate.postForEntity(url, request, Map.class);
        if (!response.getStatusCode().is2xxSuccessful()) {
            throw new IllegalStateException("HTTP " + response.getStatusCode().value());
        }
        Map<?, ?> body = response.getBody();
        if (body != null && body.containsKey("accepted")) {
            Object accepted = body.get("accepted");
            if (accepted instanceof Boolean bool && !bool) {
                Object message = body.get("message");
                throw new IllegalStateException(message == null ? "python declined task" : String.valueOf(message));
            }
        }
    }

    private DecisionTaskItemVO toTaskItem(PricingTask task) {
        Product product = productMapper.selectById(task.getProductId());
        PricingResult result = getResultByTaskId(task.getId());
        DecisionTaskItemVO vo = new DecisionTaskItemVO();
        vo.setId(task.getId());
        vo.setTaskCode(task.getTaskCode());
        vo.setProductId(task.getProductId());
        vo.setProductTitle(product == null ? "-" : product.getTitle());
        vo.setCurrentPrice(task.getCurrentPrice());
        vo.setSuggestedMinPrice(task.getSuggestedMinPrice());
        vo.setSuggestedMaxPrice(task.getSuggestedMaxPrice());
        vo.setFinalPrice(result == null ? null : result.getFinalPrice());
        vo.setTaskStatus(task.getTaskStatus());
        vo.setExecuteStrategy(result == null ? null : result.getExecuteStrategy());
        vo.setCreatedAt(task.getCreatedAt());
        return vo;
    }

    private List<DecisionComparisonVO> buildComparisonRows(Long taskId) {
        PricingTask task = taskMapper.selectById(taskId);
        if (task == null) {
            return new ArrayList<>();
        }
        Product product = productMapper.selectById(task.getProductId());
        PricingResult result = getResultByTaskId(taskId);
        if (product == null || result == null) {
            return new ArrayList<>();
        }

        DecisionComparisonVO vo = new DecisionComparisonVO();
        vo.setResultId(result.getId());
        vo.setProductId(product.getId());
        vo.setProductTitle(product.getTitle());
        vo.setOriginalPrice(task.getCurrentPrice());
        vo.setSuggestedPrice(result.getFinalPrice());
        vo.setProfitChange(result.getProfitGrowth());
        vo.setExpectedSales(result.getExpectedSales());
        vo.setExpectedProfit(result.getExpectedProfit());
        vo.setPassStatus(result.getIsPass() != null && result.getIsPass() == 1 ? "通过" : "待审核");
        vo.setExecuteStrategy(result.getExecuteStrategy());
        vo.setResultSummary(result.getResultSummary());
        vo.setAppliedStatus(isApplied(product, result) ? "已应用" : "未应用");
        return List.of(vo);
    }

    private boolean isApplied(Product product, PricingResult result) {
        if (product == null || result == null || product.getCurrentPrice() == null || result.getFinalPrice() == null) {
            return false;
        }
        return product.getCurrentPrice().setScale(2, RoundingMode.HALF_UP)
                .compareTo(result.getFinalPrice().setScale(2, RoundingMode.HALF_UP)) == 0;
    }

    private PricingResult getResultByTaskId(Long taskId) {
        LambdaQueryWrapper<PricingResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(PricingResult::getTaskId, taskId).last("LIMIT 1");
        return resultMapper.selectOne(wrapper);
    }

    private LocalDateTime parseDateTime(String text, boolean endOfDay) {
        if (text == null || text.isBlank()) {
            return null;
        }
        String trimmed = text.trim();
        try {
            return LocalDateTime.parse(trimmed, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        } catch (Exception ignore) {
        }
        try {
            LocalDate date = LocalDate.parse(trimmed, DateTimeFormatter.ofPattern("yyyy-MM-dd"));
            return endOfDay ? date.atTime(23, 59, 59) : date.atStartOfDay();
        } catch (Exception ignore) {
            return null;
        }
    }

    private BigDecimal scaleMoney(BigDecimal value) {
        if (value == null) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }
}
