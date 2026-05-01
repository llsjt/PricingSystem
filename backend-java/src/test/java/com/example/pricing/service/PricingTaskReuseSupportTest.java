package com.example.pricing.service;

import com.example.pricing.mapper.PricingTaskMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;

class PricingTaskReuseSupportTest {

    @Test
    void buildIdempotencyKeyCanonicalizesEquivalentJsonConstraints() {
        PricingTaskReuseSupport support = new PricingTaskReuseSupport(mock(PricingTaskMapper.class));

        String first = support.buildIdempotencyKey(
                List.of(221L),
                "MAX_PROFIT",
                "{\"max_price\":99.99,\"min_profit_rate\":0.15}",
                1L
        );
        String second = support.buildIdempotencyKey(
                List.of(221L),
                "MAX_PROFIT",
                "{ \"min_profit_rate\" : 0.15, \"max_price\" : 99.99 }",
                1L
        );

        assertEquals(first, second);
    }
}
