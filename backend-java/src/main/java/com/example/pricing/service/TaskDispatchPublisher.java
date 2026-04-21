package com.example.pricing.service;

import com.example.pricing.dto.TaskDispatchEvent;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.ReturnedMessage;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
public class TaskDispatchPublisher {

    private final RabbitTemplate rabbitTemplate;
    private final ConcurrentMap<String, ReturnedMessage> returnedMessages = new ConcurrentHashMap<>();

    @Value("${app.rabbitmq.dispatch-exchange}")
    private String dispatchExchange;

    @Value("${app.rabbitmq.dispatch-routing-key}")
    private String dispatchRoutingKey;

    @Value("${app.rabbitmq.publish-confirm-timeout-ms:5000}")
    private long confirmTimeoutMs;

    private Duration confirmTimeout = Duration.ofSeconds(5);

    @PostConstruct
    void configureTemplate() {
        rabbitTemplate.setMandatory(true);
        rabbitTemplate.setReturnsCallback(returned -> {
            String correlationId = returned.getMessage().getMessageProperties().getCorrelationId();
            if (correlationId != null && !correlationId.isBlank()) {
                returnedMessages.put(correlationId, returned);
            }
        });
        confirmTimeout = Duration.ofMillis(Math.max(confirmTimeoutMs, 1L));
    }

    public void publishAndConfirm(TaskDispatchEvent event) {
        String eventId = Objects.requireNonNull(event.eventId(), "eventId must not be null");
        CorrelationData correlationData = new CorrelationData(eventId);
        try {
            rabbitTemplate.convertAndSend(
                    dispatchExchange,
                    dispatchRoutingKey,
                    event,
                    message -> {
                        message.getMessageProperties().setCorrelationId(eventId);
                        message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                        return message;
                    },
                    correlationData
            );

            CorrelationData.Confirm confirm = correlationData.getFuture()
                    .get(confirmTimeout.toMillis(), TimeUnit.MILLISECONDS);
            ReturnedMessage returned = returnedMessages.get(eventId);
            if (returned != null) {
                throw new IllegalStateException("dispatch message returned: " + returned.getReplyText());
            }
            if (!confirm.isAck()) {
                throw new IllegalStateException("dispatch message confirm nack: " + confirm.getReason());
            }
        } catch (AmqpException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("dispatch message publish failed: " + e.getMessage(), e);
        } finally {
            returnedMessages.remove(eventId);
        }
    }
}
