package com.example.pricing.exception;

import com.example.pricing.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        log.error("Global Exception: ", e);
        if (e.getMessage() != null && e.getMessage().contains("无权")) {
            return Result.error(e.getMessage());
        }
        return Result.error("服务器内部错误：" + e.getMessage());
    }
    
    @ExceptionHandler(IllegalArgumentException.class)
    public Result<Void> handleIllegalArgumentException(IllegalArgumentException e) {
        log.error("Illegal Argument Exception: ", e);
        return Result.error("参数错误：" + e.getMessage());
    }
}
