package com.example.pricing.exception;

/**
 * 无权限异常，表示当前用户已登录但不具备执行操作的权限。
 */
public class ForbiddenException extends RuntimeException {
    public ForbiddenException(String message) {
        super(message);
    }
}
