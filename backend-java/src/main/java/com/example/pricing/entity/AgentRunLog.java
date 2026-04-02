package com.example.pricing.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * Agent 运行日志实体，对应多智能体在任务中的发言、证据和结论记录。
 */
@Data
@TableName("agent_run_log")
public class AgentRunLog {
    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("task_id")
    private Long taskId;

    @TableField("role_name")
    private String roleName;

    @TableField("speak_order")
    private Integer speakOrder;

    @TableField("thought_content")
    private String thoughtContent;

    @TableField("thinking_summary")
    private String thinkingSummary;

    @TableField("evidence_json")
    private String evidenceJson;

    @TableField("suggestion_json")
    private String suggestionJson;

    @TableField("final_reason")
    private String finalReason;

    @TableField("display_order")
    private Integer displayOrder;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
