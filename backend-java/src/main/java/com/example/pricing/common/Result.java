package com.example.pricing.common;

import lombok.Data;
import org.slf4j.MDC;

@Data
public class Result<T> {
    private Integer code;
    private String message;
    private T data;
    private String traceId;

    private static <T> Result<T> base(int code, String message, T data) {
        Result<T> result = new Result<>();
        result.setCode(code);
        result.setMessage(message);
        result.setData(data);
        result.setTraceId(MDC.get("traceId"));
        return result;
    }

    public static <T> Result<T> success(T data) {
        return base(200, "Success", data);
    }

    public static <T> Result<T> success() {
        return success(null);
    }

    public static <T> Result<T> error(String message) {
        return error(500, message);
    }

    public static <T> Result<T> error(int code, String message) {
        return base(code, message, null);
    }
}
