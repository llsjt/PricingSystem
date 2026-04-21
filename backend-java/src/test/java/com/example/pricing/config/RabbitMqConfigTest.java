package com.example.pricing.config;

import com.example.pricing.dto.TaskDispatchEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RabbitMqConfigTest {

    @Test
    void declaresDurableDispatchTopologyAndJacksonConverter() {
        RabbitMqConfig config = new RabbitMqConfig();
        ReflectionTestUtils.setField(config, "dispatchExchangeName", "pricing.task.dispatch.exchange");
        ReflectionTestUtils.setField(config, "dispatchQueueName", "pricing.task.dispatch.queue");
        ReflectionTestUtils.setField(config, "dispatchRoutingKey", "pricing.task.dispatch");

        DirectExchange exchange = config.dispatchExchange();
        Queue queue = config.dispatchQueue();
        Binding binding = config.dispatchBinding(queue, exchange);

        assertEquals("pricing.task.dispatch.exchange", exchange.getName());
        assertTrue(exchange.isDurable());
        assertEquals("pricing.task.dispatch.queue", queue.getName());
        assertTrue(queue.isDurable());
        assertEquals("pricing.task.dispatch", binding.getRoutingKey());

        Object converter = config.jsonMessageConverter(new ObjectMapper());
        assertInstanceOf(Jackson2JsonMessageConverter.class, converter);
    }

    @Test
    void rabbitTemplateUsesJacksonConverterAndMandatoryReturns() {
        RabbitMqConfig config = new RabbitMqConfig();
        Jackson2JsonMessageConverter converter = new Jackson2JsonMessageConverter(new ObjectMapper());

        RabbitTemplate template = config.rabbitTemplate(null, converter);

        assertEquals(converter, template.getMessageConverter());
        assertTrue(template.isMandatoryFor(new Message(new byte[0], new MessageProperties())));
    }

    @Test
    void dispatchEventSerializesInstantAsIsoString() throws Exception {
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        TaskDispatchEvent event = new TaskDispatchEvent(
                "evt-1",
                123L,
                "trace-1",
                Instant.parse("2026-04-21T04:39:00.123Z")
        );

        String json = objectMapper.writeValueAsString(event);

        assertTrue(json.contains("\"occurredAt\":\"2026-04-21T04:39:00.123Z\""));
    }
}
