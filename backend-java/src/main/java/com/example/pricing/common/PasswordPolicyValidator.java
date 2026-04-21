package com.example.pricing.common;

/**
 * 密码策略校验工具，用于检查密码强度是否符合系统要求。
 */
public final class PasswordPolicyValidator {

    private PasswordPolicyValidator() {
    }

    public static void validate(String password) {
        com.example.pricing.security.PasswordPolicyValidator.validate(password);
    }
}
