package com.example.pricing.common;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-256-GCM encryption/decryption utility for protecting user LLM API keys at rest.
 *
 * <p>Cipher output layout: {@code IV (12 bytes) || ciphertext || GCM auth tag (16 bytes)},
 * returned as a single Base64 string.</p>
 */
public final class AesGcmUtil {

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int IV_LENGTH_BYTES = 12;
    private static final int TAG_LENGTH_BITS = 128;

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private AesGcmUtil() {
        // utility class
    }

    /**
     * Encrypt plaintext with AES-256-GCM.
     *
     * @param plaintext    the string to encrypt
     * @param base64Secret Base64-encoded 32-byte AES key
     * @return Base64-encoded bytes of {@code IV + ciphertext + tag}
     * @throws IllegalStateException if encryption fails
     */
    public static String encrypt(String plaintext, String base64Secret) {
        try {
            byte[] keyBytes = Base64.getDecoder().decode(base64Secret);
            SecretKeySpec keySpec = new SecretKeySpec(keyBytes, ALGORITHM);

            byte[] iv = new byte[IV_LENGTH_BYTES];
            SECURE_RANDOM.nextBytes(iv);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec gcmSpec = new GCMParameterSpec(TAG_LENGTH_BITS, iv);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, gcmSpec);

            byte[] ciphertext = cipher.doFinal(plaintext.getBytes(java.nio.charset.StandardCharsets.UTF_8));

            // Concatenate IV + ciphertext (which already includes the GCM auth tag)
            byte[] result = new byte[IV_LENGTH_BYTES + ciphertext.length];
            System.arraycopy(iv, 0, result, 0, IV_LENGTH_BYTES);
            System.arraycopy(ciphertext, 0, result, IV_LENGTH_BYTES, ciphertext.length);

            return Base64.getEncoder().encodeToString(result);
        } catch (Exception e) {
            throw new IllegalStateException("AES-GCM encryption failed: " + e.getMessage(), e);
        }
    }

    /**
     * Decrypt a Base64-encoded AES-256-GCM ciphertext.
     *
     * @param cipherBase64 Base64-encoded bytes of {@code IV + ciphertext + tag}
     * @param base64Secret Base64-encoded 32-byte AES key
     * @return the original plaintext
     * @throws IllegalStateException if decryption fails (wrong key, tampered data, etc.)
     */
    public static String decrypt(String cipherBase64, String base64Secret) {
        try {
            byte[] keyBytes = Base64.getDecoder().decode(base64Secret);
            SecretKeySpec keySpec = new SecretKeySpec(keyBytes, ALGORITHM);

            byte[] decoded = Base64.getDecoder().decode(cipherBase64);
            if (decoded.length < IV_LENGTH_BYTES) {
                throw new IllegalArgumentException("Ciphertext too short to contain IV");
            }

            byte[] iv = new byte[IV_LENGTH_BYTES];
            System.arraycopy(decoded, 0, iv, 0, IV_LENGTH_BYTES);

            byte[] ciphertext = new byte[decoded.length - IV_LENGTH_BYTES];
            System.arraycopy(decoded, IV_LENGTH_BYTES, ciphertext, 0, ciphertext.length);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec gcmSpec = new GCMParameterSpec(TAG_LENGTH_BITS, iv);
            cipher.init(Cipher.DECRYPT_MODE, keySpec, gcmSpec);

            byte[] plainBytes = cipher.doFinal(ciphertext);
            return new String(plainBytes, java.nio.charset.StandardCharsets.UTF_8);
        } catch (IllegalStateException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("AES-GCM decryption failed: " + e.getMessage(), e);
        }
    }

    /**
     * Mask an API key for safe display, e.g. {@code sk-****abcd}.
     *
     * <p>Shows the first 3 characters, four asterisks, and the last 4 characters.
     * If the key is shorter than 8 characters, returns all asterisks of the same length.</p>
     *
     * @param apiKey the raw API key
     * @return masked representation
     */
    public static String maskApiKey(String apiKey) {
        if (apiKey == null || apiKey.isEmpty()) {
            return "****";
        }
        if (apiKey.length() < 8) {
            return "*".repeat(apiKey.length());
        }
        return apiKey.substring(0, 3) + "****" + apiKey.substring(apiKey.length() - 4);
    }
}
