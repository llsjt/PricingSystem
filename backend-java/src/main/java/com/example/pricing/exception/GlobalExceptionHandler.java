package com.example.pricing.exception;

import com.example.pricing.common.Result;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(UnauthorizedException.class)
    public Result<Void> handleUnauthorized(UnauthorizedException e, HttpServletResponse response) {
        response.setStatus(401);
        return Result.error(e.getMessage());
    }

    @ExceptionHandler(ForbiddenException.class)
    public Result<Void> handleForbidden(ForbiddenException e, HttpServletResponse response) {
        response.setStatus(403);
        return Result.error(e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        log.error("Global Exception: ", e);
        return Result.error("服务器内部错误：" + e.getMessage());
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public Result<Void> handleIllegalArgumentException(IllegalArgumentException e) {
        log.error("Illegal Argument Exception: ", e);
        return Result.error("参数错误：" + e.getMessage());
    }
}
