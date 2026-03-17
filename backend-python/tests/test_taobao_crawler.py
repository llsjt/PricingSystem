# -*- coding: utf-8 -*-
"""
测试淘宝 Web 爬虫（Selenium + Chrome）
"""

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.taobao_web_crawler import TaobaoWebCrawler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_taobao_crawler():
    """测试淘宝爬虫"""
    print("=" * 60)
    print("测试淘宝 Web 爬虫（Selenium + Chrome）")
    print("=" * 60)
    
    try:
        # 创建爬虫实例
        crawler = TaobaoWebCrawler()
        
        # 搜索商品
        keyword = "蓝牙耳机"
        print(f"\n🔍 搜索关键词：{keyword}")
        
        products = crawler.search_products(keyword, limit=5)
        
        # 打印结果
        print(f"\n✅ 成功爬取 {len(products)} 个商品\n")
        
        for i, prod in enumerate(products, 1):
            print(f"{i}. {prod.title}")
            print(f"   价格：¥{prod.price}")
            print(f"   销量：{prod.sales_volume}")
            print(f"   店铺：{prod.shop_name} ({prod.shop_type})")
            print(f"   链接：{prod.product_url}")
            print("-" * 60)
        
        if len(products) > 0:
            print("\n✅ 爬虫测试成功！")
        else:
            print("\n⚠️  未找到商品，可能是淘宝反爬或选择器需要更新")
        
        return len(products) > 0
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_competitor_crawler():
    """测试竞品爬虫集成"""
    print("\n" + "=" * 60)
    print("测试竞品爬虫服务（集成淘宝 Web 爬虫）")
    print("=" * 60)
    
    try:
        from app.services.competitor_crawler import competitor_crawler
        
        # 搜索竞品
        competitors = competitor_crawler.search_competitors(
            keyword="蓝牙耳机",
            category="数码配件",
            platforms=['taobao'],
            limit=5
        )
        
        print(f"\n✅ 成功爬取 {len(competitors)} 个竞品\n")
        
        for i, comp in enumerate(competitors, 1):
            print(f"{i}. {comp.product_name}")
            print(f"   价格：¥{comp.price}")
            print(f"   销量：{comp.sales_volume}")
            print(f"   评分：{comp.rating}")
            print(f"   店铺：{comp.shop_name} ({comp.shop_type})")
            print("-" * 60)
        
        if len(competitors) > 0:
            print("\n✅ 竞品爬虫测试成功！")
        else:
            print("\n⚠️  未找到竞品")
        
        return len(competitors) > 0
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 测试 1: 直接测试淘宝爬虫
    success1 = test_taobao_crawler()
    
    # 测试 2: 测试竞品爬虫集成
    success2 = test_competitor_crawler()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"淘宝爬虫测试：{'✅ 通过' if success1 else '❌ 失败'}")
    print(f"竞品爬虫集成测试：{'✅ 通过' if success2 else '❌ 失败'}")
    
    if success1 and success2:
        print("\n🎉 所有测试通过！爬虫可以正常使用。")
        sys.exit(0)
    else:
        print("\n⚠️  部分测试失败，请检查日志。")
        sys.exit(1)
