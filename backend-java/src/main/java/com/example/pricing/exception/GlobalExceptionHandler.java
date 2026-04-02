package com.example.pricing.exception;

import com.example.pricing.common.Result;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器，将常见异常转换为统一的接口返回格式。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 处理未登录或登录过期场景。
     */
    @ExceptionHandler(UnauthorizedException.class)
    public Result<Void> handleUnauthorized(UnauthorizedException e, HttpServletResponse response) {
        response.setStatus(401);
        return Result.error(e.getMessage());
    }

    /**
     * 处理已登录但无权限访问的场景。
     */
    @ExceptionHandler(ForbiddenException.class)
    public Result<Void> handleForbidden(ForbiddenException e, HttpServletResponse response) {
        response.setStatus(403);
        return Result.error(e.getMessage());
    }

    /**
     * 兜底处理未分类异常，避免异常栈直接暴露给前端。
     */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        log.error("Global Exception: ", e);
        return Result.error("服务器内部错误：" + e.getMessage());
    }

    /**
     * 处理参数不合法异常，向前端返回更明确的输入错误提示。
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public Result<Void> handleIllegalArgumentException(IllegalArgumentException e) {
        log.error("Illegal Argument Exception: ", e);
        return Result.error("参数错误：" + e.getMessage());
    }
}
