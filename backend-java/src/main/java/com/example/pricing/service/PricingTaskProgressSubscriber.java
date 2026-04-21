package com.example.pricing.service;

import com.example.pricing.dto.TaskProgressEvent;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Service;

import java.io.IOException;

@Service
@RequiredArgsConstructor
public class PricingTaskProgressSubscriber {

    private final PricingTaskStreamService pricingTaskStreamService;

    @RabbitListener(queues = "${app.rabbitmq.progress-queue}")
    public void onProgress(TaskProgressEvent event, Channel channel,
                           @Header(AmqpHeaders.DELIVERY_TAG) long tag) throws IOException {
        pricingTaskStreamService.handleProgressEvent(event);
        channel.basicAck(tag, false);
    }
}
