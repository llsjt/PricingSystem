package com.example.pricing.aspect;

import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.annotation.AfterReturning;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.springframework.stereotype.Component;

/**
 * 控制器调用日志切面，用于在接口执行成功后记录基础访问信息。
 */
@Aspect
@Component
@Slf4j
public class OperationLogAspect {

    /**
     * 拦截所有控制器层方法，统一作为操作日志的切入点。
     */
    @Pointcut("execution(* com.example.pricing.controller.*.*(..))")
    public void controllerPointcut() {
    }

    /**
     * 在控制器方法返回后记录调用类、方法和返回情况。
     */
    @AfterReturning(pointcut = "controllerPointcut()", returning = "result")
    public void afterReturning(JoinPoint joinPoint, Object result) {
        String methodName = joinPoint.getSignature().getName();
        String className = joinPoint.getTarget().getClass().getSimpleName();
        log.info("Operation Log - Method: {}.{}, Result: {}", className, methodName, result != null ? "Success" : "Null");
    }
}
