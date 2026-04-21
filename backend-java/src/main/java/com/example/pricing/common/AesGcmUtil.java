/*
 * AES-GCM 加解密工具，用于保护敏感配置字段的存储安全。
 */

package com.example.pricing.common;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-256-GCM 加解密工具，用于保护用户大模型 API Key 等敏感字段的落库存储。
 *
 * <p>密文布局为 {@code IV(12字节) + ciphertext + GCM认证标签(16字节)}，
 * 最终统一编码成一个 Base64 字符串进行保存。</p>
 */
public final class AesGcmUtil {

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int IV_LENGTH_BYTES = 12;
    private static final int TAG_LENGTH_BITS = 128;

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private AesGcmUtil() {
        // 工具类不允许创建实例。
    }

    /**
     * 使用 AES-256-GCM 加密明文。
     *
     * @param plaintext    待加密的原始字符串
     * @param base64Secret Base64 编码的 32 字节 AES 密钥
     * @return Base64 编码后的 {@code IV + ciphertext + tag}
     * @throws IllegalStateException 加密失败时抛出
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

            // 将随机 IV 与密文拼接，密文本身已经包含 GCM 认证标签。
            byte[] result = new byte[IV_LENGTH_BYTES + ciphertext.length];
            System.arraycopy(iv, 0, result, 0, IV_LENGTH_BYTES);
            System.arraycopy(ciphertext, 0, result, IV_LENGTH_BYTES, ciphertext.length);

            return Base64.getEncoder().encodeToString(result);
        } catch (Exception e) {
            throw new IllegalStateException("AES-GCM encryption failed: " + e.getMessage(), e);
        }
    }

    /**
     * 解密一个经过 Base64 编码的 AES-256-GCM 密文。
     *
     * @param cipherBase64 Base64 编码后的 {@code IV + ciphertext + tag}
     * @param base64Secret Base64 编码的 32 字节 AES 密钥
     * @return 解密得到的原始明文
     * @throws IllegalStateException 解密失败时抛出，例如密钥错误或密文被篡改
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
     * 将 API Key 脱敏后用于界面展示，例如 {@code sk-****abcd}。
     *
     * <p>默认保留前 3 位和后 4 位，中间替换为四个星号；
     * 如果原始长度不足 8 位，则返回等长星号字符串。</p>
     *
     * @param apiKey 原始 API Key
     * @return 脱敏后的展示字符串
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
