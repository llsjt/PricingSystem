package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.vo.DecisionComparisonVO;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.DecisionTaskItemVO;
import com.example.pricing.vo.PricingTaskDetailVO;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.util.List;
import java.util.Map;

public interface DecisionTaskService {
    Long createPricingTask(Long productId, String strategyGoal, String constraints);

    Long startTask(List<Long> productIds, String strategyGoal, String constraints);

    List<DecisionComparisonVO> getTaskResult(Long taskId);

    List<DecisionLogVO> getTaskLogs(Long taskId);

    Page<DecisionTaskItemVO> getTasks(int page, int size, String status, String startTime, String endTime, String sortOrder);

    Map<String, Long> getTaskStats(String startTime, String endTime);

    List<DecisionComparisonVO> getTaskComparison(Long taskId);

    PricingTaskDetailVO getTaskDetail(Long taskId);

    void applyDecision(Long resultId);

    void exportDecisionReport(Long taskId, HttpServletResponse response) throws IOException;
}
