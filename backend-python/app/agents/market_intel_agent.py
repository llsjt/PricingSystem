from typing import List, Dict, Any, Tuple, Optional
from app.schemas.decision import (
    AnalysisRequest, 
    MarketIntelResult,
    CompetitorInfo,
    CompetitorData,
    ReviewData
)
from app.services.competitor_crawler import competitor_crawler
import logging
from collections import Counter

logger = logging.getLogger(__name__)

class MarketIntelAgent:
    """
    MarketIntelAgent（市场情报专家）
    
    核心职责：
    - 基于外部市场数据，分析竞争格局和消费者情感
    - 竞品价格监控与对比
    - 市场竞争强度评估
    - 消费者情感分析（评论、评分）
    - 竞品促销活动监测
    - 市场份额估算
    
    不负责：
    - 内部销量分析（交给 DataAnalysisAgent）
    - 利润计算（交给 RiskControlAgent）
    """

    # 类常量：情感分析词典
    POSITIVE_KEYWORDS = {
        'zh': ["好", "不错", "喜欢", "棒", "值", "快", "满意", "优秀", "推荐", "好评", 
               "质量", "实惠", "划算", "正品", "物流快", "包装好", "客服好"],
        'en': ["good", "great", "love", "excellent", "best", "perfect", "recommend", 
               "satisfied", "amazing", "wonderful", "fast", "quality", "value"]
    }
    
    NEGATIVE_KEYWORDS = {
        'zh': ["差", "慢", "贵", "坏", "烂", "不喜欢", "失望", "垃圾", "假货", "劣质",
               "破损", "差评", "投诉", "退货", "退款", "坑", "忽悠"],
        'en': ["bad", "slow", "expensive", "hate", "worst", "terrible", "disappointed",
               "poor", "fake", "broken", "defective", "refund", "return", "complaint"]
    }
    
    PROMOTION_KEYWORDS = ["降价", "促销", "打折", "优惠", "满减", "清仓", "特价", "秒杀", 
                         "sale", "discount", "off", "deal", "promotion", "coupon"]

    def __init__(self):
        """初始化 Agent"""
        self.crawler = competitor_crawler
    
    def analyze(self, request: AnalysisRequest) -> MarketIntelResult:
        """
        执行市场情报分析任务的主入口
        
        :param request: 包含商品、销量、竞品等全量信息的请求对象
        :return: MarketIntelResult 结构化分析结果
        """
        try:
            product = request.product
            competitor_data = request.competitor_data
            reviews = request.customer_reviews
            
            # 1. 如果竞品数据为空，调用爬虫获取
            if not competitor_data.competitors or len(competitor_data.competitors) == 0:
                logger.info(f"竞品数据为空，调用爬虫获取：{product.product_name}")
                crawled_competitors = self._crawl_competitor_data(product.product_name, product.category)
                if crawled_competitors:
                    competitor_data.competitors = crawled_competitors
            
            # 2. 竞品数据预处理
            valid_competitors = self._filter_valid_competitors(competitor_data.competitors)
            
            # 2. 价格定位分析（多维度）
            (price_position, percentile, price_gap, 
             price_details) = self._analyze_price_position_comprehensive(
                product.current_price,
                product.original_price,
                valid_competitors
            )
            
            # 3. 竞争强度评估（多维度）
            (competition_level, competition_score, 
             competition_details) = self._assess_competition_level_comprehensive(
                valid_competitors,
                competitor_data.category_total_sales,
                competitor_data.top_3_brand_share,
                competitor_data.upcoming_platform_events
            )
            
            # 4. 消费者情感分析（基于评论）
            (sentiment_score, sentiment_label, 
             sentiment_details) = self._analyze_sentiment_comprehensive(
                reviews,
                valid_competitors
            )
            
            # 5. 市场份额估算
            market_share, share_trend = self._estimate_market_share(
                product.product_id,
                valid_competitors,
                competitor_data.category_total_sales
            )
            
            # 6. 生成市场建议（基于规则 + 数据驱动）
            (market_suggestion, confidence, reasons, 
             suggestion_details) = self._generate_market_suggestion_comprehensive(
                price_position, percentile, price_gap,
                competition_level, competition_score,
                sentiment_score, sentiment_label,
                market_share,
                request.strategy_goal
            )
            market_suggestion, reasons = self._apply_constraint_guardrails(
                request,
                market_suggestion,
                reasons,
            )
            
            # 7. 构造分析详情（可解释性）
            analysis_details = {
                "price_position_analysis": price_details,
                "competition_analysis": competition_details,
                "sentiment_analysis": sentiment_details,
                "market_share_estimation": {
                    "estimated_share": market_share,
                    "trend": share_trend
                }
            }
            
            # 8. 数据来源说明
            data_sources = self._get_data_sources(competitor_data, reviews)
            
            # 9. 返回结构化结果
            return MarketIntelResult(
                competition_level=competition_level,
                competition_score=competition_score,
                price_position=price_position,
                price_percentile=percentile,
                min_competitor_price=min((c.current_price for c in valid_competitors), default=None),
                max_competitor_price=max((c.current_price for c in valid_competitors), default=None),
                avg_competitor_price=sum((c.current_price for c in valid_competitors)) / len(valid_competitors) if valid_competitors else None,
                price_gap_vs_avg=price_gap,
                active_competitor_promotions=self._get_active_promotions(valid_competitors),
                upcoming_events=competitor_data.upcoming_platform_events or [],
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                top_positive_keywords=sentiment_details.get('top_positive_keywords', []),
                top_negative_keywords=sentiment_details.get('top_negative_keywords', []),
                estimated_market_share=market_share,
                market_share_trend=share_trend,
                market_suggestion=market_suggestion,
                suggestion_confidence=confidence,
                suggestion_reasons=reasons,
                analysis_details=analysis_details,
                data_sources=data_sources,
                limitations=self._get_analysis_limitations(competitor_data, reviews)
            )
            
        except Exception as e:
            logger.error(f"MarketIntelAgent 分析失败：{e}", exc_info=True)
            # 返回降级结果
            return self._get_fallback_result(request)

    def _filter_valid_competitors(self, competitors: List[CompetitorInfo]) -> List[CompetitorInfo]:
        """
        过滤有效竞品（剔除异常数据）
        """
        if not competitors:
            return []
        
        valid = []
        prices = [c.current_price for c in competitors if c.current_price > 0]
        
        if not prices:
            return competitors
        
        # 计算价格中位数和标准差
        median_price = sorted(prices)[len(prices) // 2]
        avg_price = sum(prices) / len(prices)
        std_price = (sum((p - avg_price) ** 2 for p in prices) / len(prices)) ** 0.5 if len(prices) > 1 else 0
        
        for competitor in competitors:
            # 剔除价格为 0 或负数的
            if competitor.current_price <= 0:
                continue
            
            # 剔除价格异常（如标错价）
            if std_price > 0 and abs(competitor.current_price - avg_price) > 3 * std_price:
                logger.warning(f"剔除竞品{competitor.competitor_id}，价格异常：{competitor.current_price}")
                continue
            
            valid.append(competitor)
        
        return valid if valid else competitors

    def _analyze_price_position_comprehensive(
        self,
        current_price: float,
        original_price: Optional[float],
        competitors: List[CompetitorInfo]
    ) -> Tuple[str, float, float, Dict[str, Any]]:
        """
        综合分析价格定位
        
        :return: (价格定位，分位数，与均价差距，详细分析)
        """
        if not competitors:
            return "无竞品参考", 0.5, 0.0, {"error": "无竞品数据"}
        
        competitor_prices = [c.current_price for c in competitors]
        sorted_prices = sorted(competitor_prices)
        
        # 计算分位数
        def calculate_percentile(price, sorted_list):
            if not sorted_list:
                return 0.5
            count = sum(1 for p in sorted_list if p < price)
            return count / len(sorted_list)
        
        percentile = calculate_percentile(current_price, sorted_prices)
        
        # 计算统计指标
        min_price = sorted_prices[0]
        max_price = sorted_prices[-1]
        avg_price = sum(competitor_prices) / len(competitor_prices)
        median_price = sorted_prices[len(sorted_prices) // 2]
        
        # 与均价的差距
        price_gap = (current_price - avg_price) / avg_price if avg_price > 0 else 0
        
        # 判断价格位置
        if current_price > max_price:
            position = "premium"
            position_label = "高端/独占"
        elif percentile > 0.8:
            position = "premium"
            position_label = "高端/偏高"
        elif percentile > 0.6:
            position = "mid-range"
            position_label = "中高端"
        elif percentile > 0.4:
            position = "mid-range"
            position_label = "中端/跟随"
        elif percentile > 0.2:
            position = "budget"
            position_label = "中低端/性价比"
        else:
            position = "budget"
            position_label = "低端/低价"
        
        # 检查是否有折扣
        discount_info = None
        if original_price and original_price > current_price:
            discount_rate = current_price / original_price
            discount_info = {
                "original_price": original_price,
                "discount_rate": discount_rate,
                "discount_amount": original_price - current_price
            }
        
        # 详细分析过程
        price_details = {
            "current_price": current_price,
            "competitor_count": len(competitors),
            "min_competitor_price": min_price,
            "max_competitor_price": max_price,
            "avg_competitor_price": avg_price,
            "median_competitor_price": median_price,
            "percentile": percentile,
            "price_gap_vs_avg": price_gap,
            "position": position,
            "position_label": position_label,
            "discount_info": discount_info,
            "formula": f"分位数 = {sum(1 for p in competitor_prices if p < current_price)} / {len(competitor_prices)} = {percentile:.2f}"
        }
        
        return position, percentile, price_gap, price_details

    def _assess_competition_level_comprehensive(
        self,
        competitors: List[CompetitorInfo],
        category_total_sales: Optional[int],
        cr3: Optional[float],
        upcoming_events: List[Dict[str, Any]]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        综合评估竞争强度
        
        :return: (竞争强度，竞争得分，详细分析)
        """
        if not competitors:
            return "low", 0.1, {"competitor_count": 0, "note": "无竞品数据"}
        
        # 维度 1：竞品数量（权重 30%）
        num_competitors = len(competitors)
        if num_competitors > 50:
            num_score = 30
        elif num_competitors > 20:
            num_score = 25
        elif num_competitors > 10:
            num_score = 20
        elif num_competitors > 5:
            num_score = 15
        else:
            num_score = 5
        
        # 维度 2：市场集中度 CR3（权重 30%）
        if cr3:
            if cr3 > 0.7:
                concentration_score = 10  # 寡头垄断，竞争反而不激烈
            elif cr3 > 0.5:
                concentration_score = 20
            elif cr3 > 0.3:
                concentration_score = 30
            else:
                concentration_score = 40  # 分散市场，竞争激烈
        else:
            concentration_score = 20  # 默认
        
        # 维度 3：价格离散度（权重 20%）
        prices = [c.current_price for c in competitors]
        if len(prices) > 1:
            avg_price = sum(prices) / len(prices)
            cv = (sum((p - avg_price) ** 2 for p in prices) / len(prices)) ** 0.5 / avg_price
            if cv < 0.1:
                price_variance_score = 20  # 价格高度一致，可能在打价格战
            elif cv < 0.2:
                price_variance_score = 15
            else:
                price_variance_score = 5
        else:
            price_variance_score = 10
        
        # 维度 4：促销活动频率（权重 20%）
        active_promotions = sum(1 for c in competitors if c.promotion_tags)
        promo_score = min(active_promotions * 5, 20)
        
        # 维度 5：平台活动（额外加分）
        event_penalty = 0
        if upcoming_events:
            event_penalty = 10  # 即将有大促，竞争加剧
        
        # 综合得分
        total_score = num_score + concentration_score + price_variance_score + promo_score + event_penalty
        total_score = min(100, total_score)
        
        # 判断竞争等级
        if total_score > 70:
            level = "fierce"
            level_label = "激烈"
        elif total_score > 40:
            level = "moderate"
            level_label = "中等"
        else:
            level = "low"
            level_label = "较低"
        
        # 详细分析
        competition_details = {
            "competitor_count": num_competitors,
            "num_score": num_score,
            "cr3": cr3,
            "concentration_score": concentration_score,
            "price_variance_score": price_variance_score,
            "active_promotions": active_promotions,
            "promo_score": promo_score,
            "upcoming_events": len(upcoming_events) if upcoming_events else 0,
            "event_penalty": event_penalty,
            "total_score": total_score,
            "level": level,
            "level_label": level_label,
            "formula": f"{num_score} + {concentration_score} + {price_variance_score} + {promo_score} + {event_penalty} = {total_score}"
        }
        
        return level, total_score / 100.0, competition_details

    def _analyze_sentiment_comprehensive(
        self,
        reviews: List[ReviewData],
        competitors: List[CompetitorInfo]
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        综合分析消费者情感
        
        :return: (情感得分，情感标签，详细分析)
        """
        if not reviews:
            # 无评论数据，使用竞品评论估算
            if competitors:
                avg_rating = sum((c.rating or 3.0) for c in competitors) / len(competitors)
                sentiment_score = (avg_rating - 3) / 2  # 归一化到 -1~1
                return sentiment_score, "neutral", {
                    "source": "competitor_ratings",
                    "avg_competitor_rating": avg_rating,
                    "note": "无本商品评论，使用竞品评分估算"
                }
            else:
                return 0.0, "neutral", {"note": "无评论数据"}
        
        # 情感分析
        positive_count = 0
        negative_count = 0
        positive_keywords = Counter()
        negative_keywords = Counter()
        
        for review in reviews:
            content = review.content.lower()
            tags = review.tags
            
            # 基于评分
            if review.rating >= 4:
                positive_count += 1
            elif review.rating <= 2:
                negative_count += 1
            
            # 基于关键词
            for lang in ['zh', 'en']:
                for keyword in self.POSITIVE_KEYWORDS[lang]:
                    if keyword in content or keyword in tags:
                        positive_count += 0.5
                        positive_keywords[keyword] += 1
                
                for keyword in self.NEGATIVE_KEYWORDS[lang]:
                    if keyword in content or keyword in tags:
                        negative_count += 0.5
                        negative_keywords[keyword] += 1
        
        # 计算情感得分
        total = len(reviews)
        sentiment_score = (positive_count - negative_count) / total
        sentiment_score = max(-1.0, min(1.0, sentiment_score))
        
        # 判断情感标签
        if sentiment_score > 0.3:
            sentiment_label = "positive"
        elif sentiment_score < -0.3:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"
        
        # 提取 Top 关键词
        top_positive = [kw for kw, count in positive_keywords.most_common(5)]
        top_negative = [kw for kw, count in negative_keywords.most_common(5)]
        
        # 详细分析
        sentiment_details = {
            "total_reviews": total,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "top_positive_keywords": top_positive,
            "top_negative_keywords": top_negative,
            "rating_distribution": self._calculate_rating_distribution(reviews)
        }
        
        return sentiment_score, sentiment_label, sentiment_details

    def _calculate_rating_distribution(self, reviews: List[ReviewData]) -> Dict[str, int]:
        """计算评分分布"""
        distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        for review in reviews:
            key = str(review.rating)
            if key in distribution:
                distribution[key] += 1
        return distribution

    def _estimate_market_share(
        self,
        product_id: str,
        competitors: List[CompetitorInfo],
        category_total_sales: Optional[int]
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        估算市场份额
        
        :return: (市场份额，份额趋势)
        """
        if not category_total_sales or not competitors:
            return None, None
        
        # 简化估算：假设本商品销量与竞品平均销量相当
        competitor_sales = [c.sales_volume for c in competitors if c.sales_volume]
        
        if not competitor_sales:
            return None, None
        
        avg_competitor_sales = sum(competitor_sales) / len(competitor_sales)
        estimated_own_sales = avg_competitor_sales  # 简化假设
        
        # 估算市场份额
        total_market = category_total_sales + avg_competitor_sales  # 简化
        market_share = estimated_own_sales / total_market if total_market > 0 else 0
        
        # 趋势判断（简化）
        share_trend = "stable"
        
        return market_share, share_trend

    def _get_active_promotions(self, competitors: List[CompetitorInfo]) -> List[Dict[str, Any]]:
        """获取正在进行的活动"""
        promotions = []
        for competitor in competitors:
            if competitor.promotion_tags:
                promotions.append({
                    "competitor_id": competitor.competitor_id,
                    "competitor_name": competitor.product_name,
                    "promotion_tags": competitor.promotion_tags,
                    "current_price": competitor.current_price
                })
        return promotions

    def _generate_market_suggestion_comprehensive(
        self,
        price_position: str,
        percentile: float,
        price_gap: float,
        competition_level: str,
        competition_score: float,
        sentiment_score: float,
        sentiment_label: str,
        market_share: Optional[float],
        strategy_goal: str
    ) -> Tuple[str, float, List[str], Dict[str, Any]]:
        """
        综合分析生成市场建议
        
        :return: (建议策略，置信度，理由列表，建议详情)
        """
        reasons = []
        confidence = 0.8
        suggestion = "maintain"
        
        # 策略 1：基于竞争强度
        if competition_level == "fierce":
            if price_position == "premium":
                if sentiment_label == "positive":
                    suggestion = "differentiate"
                    reasons.append("竞争激烈但口碑良好，建议差异化竞争而非价格战")
                else:
                    suggestion = "price_war"
                    confidence = 0.9
                    reasons.append("竞争激烈且价格偏高，必须跟进促销以防份额流失")
            else:
                suggestion = "penetrate"
                reasons.append("红海市场，建议保持价格优势，采用渗透定价策略")
        
        # 策略 2：基于情感分析
        elif sentiment_label == "negative":
            suggestion = "discount"
            confidence = 0.85
            reasons.append("用户口碑较差，建议通过短期降价安抚市场")
        
        # 策略 3：基于价格定位
        elif price_position == "budget" and competition_level == "low":
            suggestion = "premium"
            confidence = 0.7
            reasons.append("竞争压力小且价格偏低，建议尝试小幅提价以提升利润")
        
        # 策略 4：基于战略目标
        if strategy_goal == "MARKET_SHARE":
            if suggestion == "maintain":
                suggestion = "penetrate"
            reasons.append(f"战略目标为市场份额，建议采取更激进的定价策略")
            confidence *= 0.9
        elif strategy_goal == "MAX_PROFIT":
            if price_position == "mid-range" and sentiment_label == "positive":
                suggestion = "maintain"
                reasons.append("战略目标为利润最大化，且口碑良好，建议维持价格")
        
        # 默认情况
        if suggestion == "maintain":
            reasons.append("市场环境相对温和，建议维持当前价格策略")
        
        # 建议详情
        suggestion_details = {
            "primary_factor": "competition" if competition_level == "fierce" else "sentiment" if sentiment_label != "neutral" else "price",
            "strategy_alignment": strategy_goal,
            "confidence_factors": {
                "data_quality": 0.9,
                "market_stability": 0.8,
                "historical_accuracy": 0.85
            }
        }
        
        return suggestion, confidence, reasons, suggestion_details

    def _apply_constraint_guardrails(
        self,
        request: AnalysisRequest,
        suggestion: str,
        reasons: List[str],
    ) -> Tuple[str, List[str]]:
        risk_data = request.risk_data
        product = request.product
        min_allowed_price = risk_data.price_floor or 0.0

        if risk_data.min_profit_markup is not None:
            min_allowed_price = max(min_allowed_price, product.cost * (1 + risk_data.min_profit_markup))

        if min_allowed_price and product.current_price + 1e-6 < min_allowed_price:
            reasons.append(f"当前售价低于约束底线 {min_allowed_price:.2f} 元，市场侧不再建议降价竞争")
            return "premium", reasons

        if suggestion in {"price_war", "penetrate", "discount"} and risk_data.max_discount_allowed is not None:
            if risk_data.max_discount_allowed >= 0.999:
                reasons.append("约束条件不允许进一步降价，市场侧改为维持现价")
                return "maintain", reasons

        return suggestion, reasons

    def _get_data_sources(self, competitor_data: CompetitorData, reviews: List[ReviewData]) -> List[str]:
        """返回数据来源说明"""
        sources = []
        
        if competitor_data.competitors:
            sources.append(f"竞品数据：{len(competitor_data.competitors)}个竞品")
        
        if competitor_data.category_total_sales:
            sources.append(f"类目大盘：GMV={competitor_data.category_total_sales}")
        
        if reviews:
            sources.append(f"用户评论：{len(reviews)}条评论")
        
        if competitor_data.upcoming_platform_events:
            sources.append(f"平台活动：{len(competitor_data.upcoming_platform_events)}个即将开始")
        
        return sources

    def _get_analysis_limitations(self, competitor_data: CompetitorData, reviews: List[ReviewData]) -> List[str]:
        """返回分析局限性说明"""
        limitations = []
        
        if not competitor_data.competitors:
            limitations.append("缺少竞品数据，分析结果可能不准确")
        
        if not competitor_data.category_total_sales:
            limitations.append("缺少类目大盘数据，无法准确估算市场份额")
        
        if not reviews:
            limitations.append("缺少用户评论数据，情感分析使用竞品评分估算")
        
        if reviews and len(reviews) < 10:
            limitations.append("评论数据较少，情感分析结果仅供参考")
        
        return limitations

    def _get_fallback_result(self, request: AnalysisRequest) -> MarketIntelResult:
        """返回降级结果（当分析失败时）"""
        return MarketIntelResult(
            competition_level="moderate",
            competition_score=0.5,
            price_position="mid-range",
            price_percentile=0.5,
            min_competitor_price=None,
            max_competitor_price=None,
            avg_competitor_price=None,
            price_gap_vs_avg=0.0,
            active_competitor_promotions=[],
            upcoming_events=[],
            sentiment_score=0.0,
            sentiment_label="neutral",
            top_positive_keywords=[],
            top_negative_keywords=[],
            estimated_market_share=None,
            market_share_trend=None,
            market_suggestion="maintain",
            suggestion_confidence=0.3,
            suggestion_reasons=["市场分析失败，建议人工介入"],
            analysis_details={"error": "分析过程中发生错误"},
            data_sources=[],
            limitations=["分析失败，结果不可靠"]
        )
    
    def _crawl_competitor_data(self, product_name: str, category: str, limit: int = 10) -> List[CompetitorInfo]:
        """
        调用爬虫获取竞品数据
        
        :param product_name: 商品名称
        :param category: 商品类目
        :param limit: 爬取数量限制
        :return: 竞品信息列表
        """
        try:
            logger.info(f"开始爬取竞品数据：{product_name} ({category})")
            
            # 调用爬虫服务
            competitors = self.crawler.search_competitors(
                keyword=product_name,
                category=category,
                platforms=['tmall', 'jd'],  # 爬取天猫和京东
                limit=limit
            )
            
            # 转换为 CompetitorInfo 对象
            competitor_infos = []
            for i, comp in enumerate(competitors):
                info = CompetitorInfo(
                    competitor_id=f"CRAWLED_{i}",
                    product_name=comp.product_name,
                    current_price=comp.price,
                    original_price=comp.original_price,
                    sales_volume=comp.sales_volume,
                    rating=comp.rating,
                    review_count=comp.review_count,
                    shop_type=comp.shop_type,
                    is_self_operated=comp.is_self_operated,
                    promotion_tags=comp.promotion_tags
                )
                competitor_infos.append(info)
            
            logger.info(f"成功爬取 {len(competitor_infos)} 个竞品")
            return competitor_infos
            
        except Exception as e:
            logger.error(f"爬取失败：{e}")
            return []
