package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.AuthRefreshSession;
import org.apache.ibatis.annotations.Mapper;

/**
 * 刷新会话 Mapper，负责 auth_refresh_session 表的数据访问。
 */
@Mapper
public interface AuthRefreshSessionMapper extends BaseMapper<AuthRefreshSession> {
}
