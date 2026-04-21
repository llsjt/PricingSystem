package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.PricingTask;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

/**
 * 定价任务 Mapper，负责任务主表的增删改查。
 */
@Mapper
public interface PricingTaskMapper extends BaseMapper<PricingTask> {
    @Update("""
            UPDATE pricing_task
               SET task_status = #{status},
                   updated_at = NOW()
             WHERE id = #{taskId}
               AND task_status = 'PENDING'
            """)
    int updateStatusIfPending(@Param("taskId") Long taskId, @Param("status") String status);

    @Update("""
            UPDATE pricing_task
               SET task_status = #{status},
                   failure_reason = #{reason},
                   completed_at = NOW(),
                   updated_at = NOW()
             WHERE id = #{taskId}
            """)
    int updateStatusAndReason(@Param("taskId") Long taskId, @Param("status") String status, @Param("reason") String reason);

    @Select("""
            SELECT *
              FROM pricing_task
             WHERE task_status = 'PENDING'
               AND created_at < NOW() - INTERVAL #{minutes} MINUTE
            """)
    List<PricingTask> selectStalePendingTasks(@Param("minutes") int minutes);

    @Update("""
            UPDATE pricing_task
               SET task_status = 'CANCELLED',
                   failure_reason = '任务已取消',
                   current_execution_id = NULL,
                   completed_at = NOW(),
                   updated_at = NOW()
             WHERE id = #{taskId}
               AND task_status IN ('PENDING', 'QUEUED', 'RUNNING', 'RETRYING')
            """)
    int cancelIfRunning(@Param("taskId") Long taskId);
}
