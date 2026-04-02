package com.example.pricing.exception;

/**
 * 未认证异常，表示请求缺少登录态或登录态已经失效。
 */
public class UnauthorizedException extends RuntimeException {
    public UnauthorizedException(String message) {
        super(message);
    }
}
