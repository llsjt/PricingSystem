package com.example.pricing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.pricing.entity.UploadBatch;
import org.apache.ibatis.annotations.Mapper;

/**
 * 导入批次 Mapper，负责记录每次 Excel 导入的批次状态。
 */
@Mapper
public interface UploadBatchMapper extends BaseMapper<UploadBatch> {
}
