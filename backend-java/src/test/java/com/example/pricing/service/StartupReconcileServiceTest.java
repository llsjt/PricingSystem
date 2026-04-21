package com.example.pricing.service;

import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.PricingTaskMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class StartupReconcileServiceTest {

    @Mock
    private PricingTaskMapper taskMapper;

    @Mock
    private TaskDispatchPublisher taskDispatchPublisher;

    @Test
    void republishesStalePendingTasksAndMarksQueuedAfterConfirm() {
        PricingTask task = new PricingTask();
        task.setId(88L);
        task.setTraceId("trace-88");
        when(taskMapper.selectStalePendingTasks(5)).thenReturn(List.of(task));

        StartupReconcileService service = new StartupReconcileService(taskMapper, taskDispatchPublisher);
        service.reconcileOrphanPendingTasks();

        ArgumentCaptor<com.example.pricing.dto.TaskDispatchEvent> eventCaptor =
                ArgumentCaptor.forClass(com.example.pricing.dto.TaskDispatchEvent.class);
        verify(taskDispatchPublisher).publishAndConfirm(eventCaptor.capture());
        assertEquals(88L, eventCaptor.getValue().taskId());
        assertEquals("trace-88", eventCaptor.getValue().traceId());
        verify(taskMapper).updateStatusIfPending(88L, "QUEUED");
    }

    @Test
    void leavesPendingTaskUntouchedWhenRepublishFails() {
        PricingTask task = new PricingTask();
        task.setId(89L);
        task.setTraceId("trace-89");
        when(taskMapper.selectStalePendingTasks(5)).thenReturn(List.of(task));
        doThrow(new IllegalStateException("rabbit down")).when(taskDispatchPublisher).publishAndConfirm(org.mockito.ArgumentMatchers.any());

        StartupReconcileService service = new StartupReconcileService(taskMapper, taskDispatchPublisher);
        service.reconcileOrphanPendingTasks();

        verify(taskDispatchPublisher).publishAndConfirm(org.mockito.ArgumentMatchers.any());
    }
}
