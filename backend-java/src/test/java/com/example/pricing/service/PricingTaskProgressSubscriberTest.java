package com.example.pricing.service;

import com.example.pricing.dto.TaskProgressEvent;
import com.rabbitmq.client.Channel;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Map;

import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class PricingTaskProgressSubscriberTest {

    @Mock
    private PricingTaskStreamService pricingTaskStreamService;

    @Mock
    private Channel channel;

    @Test
    void acknowledgesMessageAfterDispatchingToStreamService() throws Exception {
        PricingTaskProgressSubscriber subscriber = new PricingTaskProgressSubscriber(pricingTaskStreamService);
        TaskProgressEvent event = new TaskProgressEvent(
                "evt-1",
                "TASK_STARTED",
                123L,
                "exec-1",
                "trace-1",
                Map.of(),
                Instant.parse("2026-04-21T04:40:00.456Z")
        );

        subscriber.onProgress(event, channel, 9L);

        verify(pricingTaskStreamService).handleProgressEvent(event);
        verify(channel).basicAck(9L, false);
    }
}
