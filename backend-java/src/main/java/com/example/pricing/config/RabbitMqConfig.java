package com.example.pricing.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.ExchangeBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * RabbitMQ 配置类，集中声明交换机、队列与绑定关系。
 */
@Configuration
public class RabbitMqConfig {

    @Value("${app.rabbitmq.dispatch-exchange}")
    private String dispatchExchangeName;

    @Value("${app.rabbitmq.dispatch-queue}")
    private String dispatchQueueName;

    @Value("${app.rabbitmq.dispatch-routing-key}")
    private String dispatchRoutingKey;

    @Value("${app.rabbitmq.progress-exchange}")
    private String progressExchangeName;

    @Value("${app.rabbitmq.progress-queue}")
    private String progressQueueName;

    @Value("${app.rabbitmq.progress-routing-key}")
    private String progressRoutingKey;

    @Bean
    public DirectExchange dispatchExchange() {
        return ExchangeBuilder.directExchange(dispatchExchangeName).durable(true).build();
    }

    @Bean
    public Queue dispatchQueue() {
        return QueueBuilder.durable(dispatchQueueName).build();
    }

    @Bean
    public Binding dispatchBinding(Queue dispatchQueue, DirectExchange dispatchExchange) {
        return BindingBuilder.bind(dispatchQueue).to(dispatchExchange).with(dispatchRoutingKey);
    }

    @Bean
    public DirectExchange progressExchange() {
        return ExchangeBuilder.directExchange(progressExchangeName).durable(true).build();
    }

    @Bean
    public Queue progressQueue() {
        return QueueBuilder.durable(progressQueueName).build();
    }

    @Bean
    public Binding progressBinding(Queue progressQueue, DirectExchange progressExchange) {
        return BindingBuilder.bind(progressQueue).to(progressExchange).with(progressRoutingKey);
    }

    @Bean
    public MessageConverter jsonMessageConverter(ObjectMapper objectMapper) {
        return new Jackson2JsonMessageConverter(objectMapper);
    }

    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory, MessageConverter jsonMessageConverter) {
        RabbitTemplate template = connectionFactory == null ? new RabbitTemplate() : new RabbitTemplate(connectionFactory);
        template.setMessageConverter(jsonMessageConverter);
        template.setMandatory(true);
        return template;
    }

    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
            ConnectionFactory connectionFactory,
            MessageConverter jsonMessageConverter
    ) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setMessageConverter(jsonMessageConverter);
        factory.setAcknowledgeMode(org.springframework.amqp.core.AcknowledgeMode.MANUAL);
        factory.setPrefetchCount(1);
        return factory;
    }

    @Bean
    public TransactionTemplate transactionTemplate(PlatformTransactionManager transactionManager) {
        return new TransactionTemplate(transactionManager);
    }
}
