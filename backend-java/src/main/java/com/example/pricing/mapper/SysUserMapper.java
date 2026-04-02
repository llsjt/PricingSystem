package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.SysUser;
import org.apache.ibatis.annotations.Mapper;

/**
 * 系统用户 Mapper，负责后台登录用户的读写。
 */
@Mapper
public interface SysUserMapper extends BaseMapper<SysUser> {
}
