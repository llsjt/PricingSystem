package com.example.pricing.security;

import com.example.pricing.entity.LoginAuditLog;
import com.example.pricing.mapper.LoginAuditLogMapper;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class LoginAuditService {

    private final LoginAuditLogMapper loginAuditLogMapper;

    public void record(Long userId, String username, HttpServletRequest request, String status, String failureReason) {
        LoginAuditLog log = new LoginAuditLog();
        log.setUserId(userId);
        log.setUsername(username);
        log.setIpAddress(resolveClientIp(request));
        log.setUserAgent(truncate(request.getHeader("User-Agent"), 255));
        log.setLoginStatus(status);
        log.setFailureReason(failureReason);
        loginAuditLogMapper.insert(log);
    }

    private String resolveClientIp(HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) {
            return truncate(forwardedFor.split(",")[0].trim(), 64);
        }
        return truncate(request.getRemoteAddr(), 64);
    }

    private String truncate(String value, int maxLength) {
        if (value == null) {
            return null;
        }
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }
}
