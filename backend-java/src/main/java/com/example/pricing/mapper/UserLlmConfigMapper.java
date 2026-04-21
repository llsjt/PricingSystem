/*
 * 用户模型配置 Mapper，负责 user_llm_config 表的数据访问。
 */

package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.UserLlmConfig;
import org.apache.ibatis.annotations.Mapper;

/**
 * 用户 LLM 配置 Mapper，负责 user_llm_config 表的增删改查。
 */
@Mapper
public interface UserLlmConfigMapper extends BaseMapper<UserLlmConfig> {
}
