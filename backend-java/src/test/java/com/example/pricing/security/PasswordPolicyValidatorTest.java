package com.example.pricing.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PasswordPolicyValidatorTest {

    @Test
    void acceptsStrongPassword() {
        assertDoesNotThrow(() -> PasswordPolicyValidator.validate("StrongPass123!"));
    }

    @Test
    void rejectsTooShortPassword() {
        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> PasswordPolicyValidator.validate("S1!abc")
        );

        assertTrue(exception.getMessage().contains("8"));
    }

    @Test
    void rejectsPasswordMissingRequiredCharacterCategories() {
        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> PasswordPolicyValidator.validate("alllowercase123")
        );

        assertTrue(exception.getMessage().contains("大写"));
    }
}
