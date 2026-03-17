package com.example.pricing.dto;

import lombok.Data;
import java.util.List;

@Data
public class DecisionTaskDTO {
    private List<Long> productIds;
    private String strategyGoal;
    private String constraints;
}
