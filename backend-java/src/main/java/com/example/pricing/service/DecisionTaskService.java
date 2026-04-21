/*
 * 决策任务服务接口，定义单商品智能定价的核心业务能力。
 */

package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.vo.DecisionComparisonVO;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.DecisionTaskItemVO;
import com.example.pricing.vo.PricingTaskDetailVO;
import com.example.pricing.vo.PricingTaskSnapshotVO;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * 定价决策任务服务接口，定义任务创建、执行结果查询和结果应用等能力。
 */
public interface DecisionTaskService {
    /**
     * 基于单个商品创建定价任务。
     */
    Long createPricingTask(Long productId, String strategyGoal, String constraints, Long userId);

    /**
     * 基于多个商品启动定价任务。
     */
    Long startTask(List<Long> productIds, String strategyGoal, String constraints, Long userId);

    /**
     * 获取任务最终结果列表。
     */
    List<DecisionComparisonVO> getTaskResult(Long taskId, Long userId);

    /**
     * 获取任务执行日志。
     */
    List<DecisionLogVO> getTaskLogs(Long taskId, Long userId);

    /**
     * 分页查询历史任务。
     */
    Page<DecisionTaskItemVO> getTasks(int page, int size, String status, String startTime, String endTime, String sortOrder, Long userId);

    /**
     * 统计任务数量。
     */
    Map<String, Long> getTaskStats(String startTime, String endTime, Long userId);

    /**
     * 获取任务价格对比数据。
     */
    List<DecisionComparisonVO> getTaskComparison(Long taskId, Long userId);

    /**
     * 获取任务详情。
     */
    PricingTaskDetailVO getTaskDetail(Long taskId, Long userId);

    PricingTaskSnapshotVO getTaskSnapshot(Long taskId, Long userId);

    /**
     * 将某条建议价格应用回商品。
     */
    void applyDecision(Long resultId, Long userId);

    void cancelTask(Long taskId, Long userId);

    /**
     * 导出任务报告。
     */
    void exportDecisionReport(Long taskId, HttpServletResponse response, Long userId) throws IOException;
}
