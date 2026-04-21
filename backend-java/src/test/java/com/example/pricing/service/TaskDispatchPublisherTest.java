package com.example.pricing.service;

import com.example.pricing.dto.TaskDispatchEvent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class TaskDispatchPublisherTest {

    private RabbitTemplate rabbitTemplate;
    private AtomicReference<RabbitTemplate.ReturnsCallback> returnsCallback;
    private TaskDispatchPublisher publisher;

    @BeforeEach
    void setUp() {
        rabbitTemplate = mock(RabbitTemplate.class);
        returnsCallback = new AtomicReference<>();
        doAnswer(invocation -> {
            returnsCallback.set(invocation.getArgument(0));
            return null;
        }).when(rabbitTemplate).setReturnsCallback(any());

        publisher = new TaskDispatchPublisher(rabbitTemplate);
        ReflectionTestUtils.setField(publisher, "dispatchExchange", "pricing.task.dispatch.exchange");
        ReflectionTestUtils.setField(publisher, "dispatchRoutingKey", "pricing.task.dispatch");
        ReflectionTestUtils.setField(publisher, "confirmTimeoutMs", 1000L);
        publisher.configureTemplate();
    }

    @Test
    void returnsOnlyAfterBrokerConfirmAck() {
        doAnswer(invocation -> {
            CorrelationData correlationData = invocation.getArgument(4);
            correlationData.getFuture().complete(new CorrelationData.Confirm(true, null));
            return null;
        }).when(rabbitTemplate).convertAndSend(eq("pricing.task.dispatch.exchange"), eq("pricing.task.dispatch"), any(), any(), any(CorrelationData.class));

        assertDoesNotThrow(() -> publisher.publishAndConfirm(event("evt-ok")));

        verify(rabbitTemplate).setMandatory(true);
        ArgumentCaptor<CorrelationData> captor = ArgumentCaptor.forClass(CorrelationData.class);
        verify(rabbitTemplate).convertAndSend(eq("pricing.task.dispatch.exchange"), eq("pricing.task.dispatch"), any(), any(), captor.capture());
        assertEquals("evt-ok", captor.getValue().getId());
    }

    @Test
    void throwsWhenBrokerConfirmNack() {
        doAnswer(invocation -> {
            CorrelationData correlationData = invocation.getArgument(4);
            correlationData.getFuture().complete(new CorrelationData.Confirm(false, "no route"));
            return null;
        }).when(rabbitTemplate).convertAndSend(eq("pricing.task.dispatch.exchange"), eq("pricing.task.dispatch"), any(), any(), any(CorrelationData.class));

        assertThrows(IllegalStateException.class, () -> publisher.publishAndConfirm(event("evt-nack")));
    }

    @Test
    void throwsWhenMandatoryReturnArrivesBeforeConfirm() {
        doAnswer(invocation -> {
            CorrelationData correlationData = invocation.getArgument(4);
            MessageProperties properties = new MessageProperties();
            properties.setCorrelationId(correlationData.getId());
            Message message = new Message(new byte[0], properties);
            returnsCallback.get().returnedMessage(new org.springframework.amqp.core.ReturnedMessage(
                    message,
                    312,
                    "NO_ROUTE",
                    "pricing.task.dispatch.exchange",
                    "pricing.task.dispatch"
            ));
            correlationData.getFuture().complete(new CorrelationData.Confirm(true, null));
            return null;
        }).when(rabbitTemplate).convertAndSend(eq("pricing.task.dispatch.exchange"), eq("pricing.task.dispatch"), any(), any(), any(CorrelationData.class));

        assertThrows(IllegalStateException.class, () -> publisher.publishAndConfirm(event("evt-return")));
    }

    private TaskDispatchEvent event(String eventId) {
        return new TaskDispatchEvent(eventId, 123L, "trace-123", Instant.parse("2026-04-21T04:39:00.123Z"));
    }
}
