package com.example.pricing.common;

import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TraceContextFilterTest {

    @Test
    void propagatesIncomingTraceIdToRequestResponseAndMdc() throws Exception {
        TraceContextFilter filter = new TraceContextFilter();
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/health/live");
        MockHttpServletResponse response = new MockHttpServletResponse();
        request.addHeader(TraceContextFilter.TRACE_HEADER, "trace-from-client");

        final String[] traceSeenInsideChain = new String[1];
        FilterChain chain = (req, res) -> traceSeenInsideChain[0] = MDC.get("traceId");

        filter.doFilter(request, response, chain);

        assertEquals("trace-from-client", request.getAttribute(TraceContextFilter.TRACE_REQUEST_ATTRIBUTE));
        assertEquals("trace-from-client", response.getHeader(TraceContextFilter.TRACE_HEADER));
        assertEquals("trace-from-client", traceSeenInsideChain[0]);
        assertNull(MDC.get("traceId"));
    }

    @Test
    void generatesTraceIdWhenRequestDoesNotProvideOne() throws Exception {
        TraceContextFilter filter = new TraceContextFilter();
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/health/live");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, (req, res) -> {
        });

        Object requestTraceId = request.getAttribute(TraceContextFilter.TRACE_REQUEST_ATTRIBUTE);
        String responseTraceId = response.getHeader(TraceContextFilter.TRACE_HEADER);

        assertNotNull(requestTraceId);
        assertNotNull(responseTraceId);
        assertEquals(requestTraceId, responseTraceId);
        assertTrue(String.valueOf(responseTraceId).startsWith("req-"));
        assertNull(MDC.get("traceId"));
    }
}
