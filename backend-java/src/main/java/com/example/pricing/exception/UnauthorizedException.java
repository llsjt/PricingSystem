/*
 * 未认证异常类型，用于表达用户尚未登录或登录态失效的场景。
 */

package com.example.pricing.exception;

/**
 * 未认证异常，表示请求缺少登录态或登录态已经失效。
 */
public class UnauthorizedException extends RuntimeException {
    public UnauthorizedException(String message) {
        super(message);
    }
}
