/*
 * 智能体日志 Mapper，负责 agent_run_log 表的数据访问。
 */

package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.AgentRunLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * Agent 执行日志 Mapper，负责读写多智能体运行过程记录。
 */
@Mapper
public interface AgentRunLogMapper extends BaseMapper<AgentRunLog> {
}
