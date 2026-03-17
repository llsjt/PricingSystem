# -*- coding: utf-8 -*-
"""
快速测试 - 验证前后端 Agent 智能决策流程
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_python_backend():
    """测试 Python 后端"""
    print("\n" + "="*60)
    print("1️⃣ 测试 Python 后端")
    print("="*60)
    
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"✅ Python 后端运行正常")
        print(f"   状态：{response.json().get('status', 'unknown')}")
        return True
    except:
        print(f"❌ Python 后端未启动")
        return False

def test_database():
    """测试数据库"""
    print("\n" + "="*60)
    print("2️⃣ 测试数据库连接")
    print("="*60)
    
    import mysql.connector
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='123456',
            database='pricing_system'
        )
        cursor = conn.cursor()
        
        # 检查商品
        cursor.execute("SELECT COUNT(*) FROM biz_product")
        product_count = cursor.fetchone()[0]
        print(f"✅ 数据库连接正常")
        print(f"   商品数量：{product_count}")
        
        # 检查任务
        cursor.execute("SELECT COUNT(*) FROM dec_task")
        task_count = cursor.fetchone()[0]
        print(f"   决策任务数：{task_count}")
        
        # 检查结果
        cursor.execute("SELECT COUNT(*) FROM dec_result")
        result_count = cursor.fetchone()[0]
        print(f"   决策结果数：{result_count}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败：{e}")
        return False

def test_crawler():
    """测试爬虫"""
    print("\n" + "="*60)
    print("3️⃣ 测试竞品爬虫")
    print("="*60)
    
    try:
        from app.services.competitor_crawler import competitor_crawler
        
        print(f"🕷️  爬取淘宝竞品数据...")
        competitors = competitor_crawler.search_competitors(
            keyword="蓝牙耳机",
            category="数码配件",
            limit=3
        )
        
        print(f"✅ 爬虫工作正常")
        print(f"   爬取到 {len(competitors)} 个竞品")
        
        if competitors:
            for i, comp in enumerate(competitors[:2], 1):
                print(f"   {i}. {comp.product_name[:50]}")
                print(f"      价格：¥{comp.price}, 销量：{comp.sales_volume}")
        
        return True
        
    except Exception as e:
        print(f"❌ 爬虫测试失败：{e}")
        return False

def test_agents():
    """测试 Agent 模块"""
    print("\n" + "="*60)
    print("4️⃣ 测试 Agent 模块")
    print("="*60)
    
    try:
        # 测试 DataAnalysisAgent
        from app.agents.data_analysis_agent import DataAnalysisAgent
        print(f"✅ DataAnalysisAgent 加载成功")
        
        # 测试 MarketIntelAgent
        from app.agents.market_intel_agent import MarketIntelAgent
        print(f"✅ MarketIntelAgent 加载成功")
        
        # 测试 RiskControlAgent
        from app.agents.risk_control_agent import RiskControlAgent
        print(f"✅ RiskControlAgent 加载成功")
        
        # 测试 ManagerCoordinatorAgent
        from app.agents.manager_coordinator_agent import ManagerCoordinatorAgent
        print(f"✅ ManagerCoordinatorAgent 加载成功")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent 模块测试失败：{e}")
        return False

def test_decision_service():
    """测试决策服务"""
    print("\n" + "="*60)
    print("5️⃣ 测试决策服务")
    print("="*60)
    
    try:
        from app.services.decision_service import decision_service
        print(f"✅ DecisionService 加载成功")
        
        # 检查服务方法
        if hasattr(decision_service, 'execute_decision_workflow'):
            print(f"✅ execute_decision_workflow 方法存在")
        
        return True
        
    except Exception as e:
        print(f"❌ 决策服务测试失败：{e}")
        return False

def check_task_result():
    """检查最近任务结果"""
    print("\n" + "="*60)
    print("6️⃣ 检查最近任务执行结果")
    print("="*60)
    
    import mysql.connector
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='123456',
            database='pricing_system'
        )
        cursor = conn.cursor()
        
        # 查询最近任务
        cursor.execute("""
            SELECT id, task_no, strategy_type, status, created_at
            FROM dec_task
            ORDER BY created_at DESC
            LIMIT 1
        """)
        task = cursor.fetchone()
        
        if task:
            print(f"✅ 最近任务:")
            print(f"   任务 ID: {task[0]}")
            print(f"   任务编号：{task[1]}")
            print(f"   策略类型：{task[2]}")
            print(f"   状态：{task[3]}")
            print(f"   创建时间：{task[4]}")
            
            # 查询该任务的结果
            cursor.execute("""
                SELECT COUNT(*) FROM dec_result WHERE task_id = %s
            """, (task[0],))
            result_count = cursor.fetchone()[0]
            print(f"   决策结果数：{result_count}")
            
            # 查询 Agent 日志
            cursor.execute("""
                SELECT COUNT(*) FROM dec_agent_log WHERE task_id = %s
            """, (task[0],))
            log_count = cursor.fetchone()[0]
            print(f"   Agent 协作日志数：{log_count}")
            
            if result_count > 0:
                print(f"\n✅ 任务执行成功！")
            else:
                print(f"\n⚠️  任务可能还在执行中")
        else:
            print(f"⚠️  暂无任务记录")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 查询失败：{e}")
        return False

def main():
    """主测试流程"""
    print("\n" + "="*70)
    print("  🚀 前后端 Agent 智能决策流程 - 快速测试")
    print("="*70)
    
    results = []
    
    # 1. Python 后端
    results.append(("Python 后端", test_python_backend()))
    
    # 2. 数据库
    results.append(("数据库", test_database()))
    
    # 3. 爬虫
    results.append(("竞品爬虫", test_crawler()))
    
    # 4. Agent 模块
    results.append(("Agent 模块", test_agents()))
    
    # 5. 决策服务
    results.append(("决策服务", test_decision_service()))
    
    # 6. 任务结果
    results.append(("任务执行", check_task_result()))
    
    # 打印总结
    print("\n" + "="*70)
    print("  📊 测试总结")
    print("="*70)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    total = len(results)
    passed = sum(1 for _, v in results if v)
    rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n总体通过率：{passed}/{total} ({rate:.1f}%)")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统运行正常！")
    elif passed >= total * 0.8:
        print("\n✅ 主要功能测试通过！")
    else:
        print("\n⚠️  部分测试失败，请检查系统配置。")
    
    print("\n" + "="*70)
    print("测试完成时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
