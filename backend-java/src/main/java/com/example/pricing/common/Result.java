package com.example.pricing.common;

import lombok.Data;

/**
 * 统一接口响应包装，约定返回码、提示信息和数据体结构。
 */
@Data
public class Result<T> {
    private Integer code;
    private String message;
    private T data;

    /**
     * 构建成功响应并携带返回数据。
     */
    public static <T> Result<T> success(T data) {
        Result<T> result = new Result<>();
        result.setCode(200);
        result.setMessage("Success");
        result.setData(data);
        return result;
    }

    /**
     * 构建不带数据的成功响应。
     */
    public static <T> Result<T> success() {
        return success(null);
    }

    /**
     * 构建失败响应并返回错误提示。
     */
    public static <T> Result<T> error(String message) {
        Result<T> result = new Result<>();
        result.setCode(500);
        result.setMessage(message);
        return result;
    }
}
