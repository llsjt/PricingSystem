package com.example.pricing.common;

public final class PasswordPolicyValidator {

    private PasswordPolicyValidator() {
    }

    public static void validate(String password) {
        com.example.pricing.security.PasswordPolicyValidator.validate(password);
    }
}
