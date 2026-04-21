package com.example.pricing.service;

import com.example.pricing.dto.TaskDispatchEvent;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.PricingTaskMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * 启动对账服务，用于应用启动后修复遗留中的任务状态。
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class StartupReconcileService {

    private final PricingTaskMapper taskMapper;
    private final TaskDispatchPublisher taskDispatchPublisher;

    @EventListener(ApplicationReadyEvent.class)
    @Scheduled(fixedDelay = 5 * 60 * 1000L)
    public void reconcileOrphanPendingTasks() {
        List<PricingTask> tasks = taskMapper.selectStalePendingTasks(5);
        for (PricingTask task : tasks) {
            TaskDispatchEvent event = new TaskDispatchEvent(
                    UUID.randomUUID().toString(),
                    task.getId(),
                    task.getTraceId(),
                    Instant.now()
            );
            try {
                taskDispatchPublisher.publishAndConfirm(event);
                taskMapper.updateStatusIfPending(task.getId(), "QUEUED");
                log.warn("re-published stale PENDING task {}", task.getId());
            } catch (Exception ex) {
                log.warn("re-publish stale PENDING task failed, taskId={}", task.getId(), ex);
            }
        }
    }
}
