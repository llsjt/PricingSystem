package com.example.pricing.security;

/**
 * 安全域密码策略校验器，服务于注册、重置和修改密码场景。
 */
public final class PasswordPolicyValidator {

    private PasswordPolicyValidator() {
    }

    public static void validate(String password) {
        if (password == null || password.length() < 8) {
            throw new IllegalArgumentException("密码长度至少需要 8 位");
        }
        if (!password.chars().anyMatch(Character::isUpperCase)) {
            throw new IllegalArgumentException("密码至少需要包含一个大写字母");
        }
        if (!password.chars().anyMatch(Character::isLowerCase)) {
            throw new IllegalArgumentException("密码至少需要包含一个小写字母");
        }
        if (!password.chars().anyMatch(Character::isDigit)) {
            throw new IllegalArgumentException("密码至少需要包含一个数字");
        }
        if (password.chars().noneMatch(ch -> !Character.isLetterOrDigit(ch))) {
            throw new IllegalArgumentException("密码至少需要包含一个特殊字符");
        }
    }
}
