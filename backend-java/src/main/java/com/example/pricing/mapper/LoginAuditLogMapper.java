package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.LoginAuditLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * 登录审计 Mapper，负责 login_audit_log 表的数据访问。
 */
@Mapper
public interface LoginAuditLogMapper extends BaseMapper<LoginAuditLog> {
}
