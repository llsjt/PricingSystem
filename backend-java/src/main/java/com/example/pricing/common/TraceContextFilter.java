package com.example.pricing.common;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * 链路追踪过滤器，为每个请求补充 traceId 并透传到日志上下文。
 */
@Component
public class TraceContextFilter extends OncePerRequestFilter {

    public static final String TRACE_HEADER = "X-Trace-Id";
    public static final String TRACE_REQUEST_ATTRIBUTE = "traceId";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String traceId = resolveTraceId(request.getHeader(TRACE_HEADER));
        request.setAttribute(TRACE_REQUEST_ATTRIBUTE, traceId);
        response.setHeader(TRACE_HEADER, traceId);
        MDC.put("traceId", traceId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove("traceId");
        }
    }

    static String resolveTraceId(String candidate) {
        if (candidate == null || candidate.isBlank()) {
            return "req-" + UUID.randomUUID().toString().replace("-", "");
        }
        return candidate.trim();
    }
}
