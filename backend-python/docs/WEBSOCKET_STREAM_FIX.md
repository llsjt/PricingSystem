# WebSocket 流式推送测试指南

## 🐛 问题描述

前端进行智能定价时，没有返回 Agent 的流式文本。

## 🔍 问题分析

### 问题 1：前端 WebSocket 处理逻辑问题

**原代码问题**：
```typescript
// 问题 1：创建消息块时没有正确初始化
chatMessages.value.push({
  agent_role: data.agent_role,  // 可能为 undefined
  step_order: data.step_order,  // 可能为 undefined
  thought_content: '',
  timestamp: data.timestamp
})

// 问题 2：追加内容时只检查最后一条消息
const lastMsg = chatMessages.value[chatMessages.value.length - 1]
if (lastMsg && lastMsg.agent_role === data.agent_role) {
  lastMsg.thought_content += data.thought_content
}
```

**修复方案**：
```typescript
// 修复 1：添加默认值和错误处理
const newMsg = {
  agent_role: data.agent_role || '未知',
  step_order: data.step_order || 0,
  thought_content: '',
  timestamp: data.timestamp || new Date().toLocaleTimeString()
}

// 修复 2：从后往前找第一个匹配角色的消息
for (let i = chatMessages.value.length - 1; i >= 0; i--) {
  const msg = chatMessages.value[i]
  if (msg.agent_role === data.agent_role && !msg.is_stream) {
    msg.thought_content += (data.thought_content || '')
    break
  }
}
```

## 📝 修改内容

### 文件：`frontend/src/views/PricingLab.vue`

**修改位置**：第 274-293 行

**修改要点**：
1. ✅ 为 `agent_role` 和 `step_order` 添加默认值
2. ✅ 为 `timestamp` 添加默认值
3. ✅ 改进流式内容追加逻辑，从后往前查找匹配的消息
4. ✅ 添加调试日志

## 🧪 测试步骤

### 步骤 1：启动后端服务

```bash
# 启动 Python 后端
cd backend-python
python app/main.py

# 应该看到：
# INFO:     Started server process [xxxxx]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://localhost:8000
```

### 步骤 2：启动前端服务

```bash
# 启动 Vue 前端
cd frontend
npm run dev

# 应该看到：
# VITE v5.x.x  ready in xxx ms
# ➜  Local:   http://localhost:5173/
# ➜  Network: use --host to expose
```

### 步骤 3：访问智能定价页面

1. 打开浏览器访问：`http://localhost:5173/pricing-lab`
2. 选择一个或多个商品
3. 选择策略目标（如：利润最大化）
4. 输入约束条件（如：利润率不低于 15%）
5. 点击"启动智能决策"

### 步骤 4：观察 WebSocket 消息

**预期效果**：

应该看到以下流程：

```
[系统] 连接成功，等待 Agent 介入...
[系统] 正在分析商品：蓝牙耳机...

[数据分析师] 正在分析商品历史数据...
[数据分析师] 分析完成。建议折扣区间：8.5 折 -9 折

[市场策略官] 正在分析市场情况...
[市场策略官] 市场建议：建议采取差异化定价策略

[财务风控官] 正在进行财务风险评估...
[财务风控官] 风控评估：安全折扣区间：8 折 -8.5 折

[首席定价官] 正在综合各方意见，制定最终决策...
[首席定价官] 最终决策：建议降价。建议价格：89.90 元。
            核心理由：基于成本利润分析和市场定位...

[系统] 商品 1 决策完成
```

**进度条应该**：
- 数据分析师开始时：25%
- 市场策略官开始时：50%
- 财务风控官开始时：75%
- 首席定价官开始时：95%
- 全部完成：100%

### 步骤 5：检查浏览器控制台

打开浏览器开发者工具（F12），查看控制台：

**应该看到**：
```
Stream end for role: 数据分析师
Stream end for role: 市场策略官
Stream end for role: 财务风控官
Stream end for role: 首席定价官
```

**不应该看到**：
```
WS Parse Error ...
```

## 🔧 故障排查

### 问题 1：WebSocket 连接失败

**症状**：
- 前端显示"连接中..."一直是黄色标签
- 没有收到任何消息

**检查**：
```bash
# 检查 Python 后端是否运行
netstat -ano | findstr :8000

# 检查 WebSocket 端点
curl -i http://localhost:8000/health
```

**解决**：
确保 Python 后端正在运行，并且 WebSocket 端点可用。

### 问题 2：收到消息但没有显示

**症状**：
- WebSocket 显示"实时连接"（绿色标签）
- 聊天框是空的

**检查**：
1. 打开浏览器开发者工具
2. 查看 Network -> WS 标签
3. 查看收到的消息

**解决**：
检查前端 `socket.onmessage` 处理逻辑，确保正确解析消息格式。

### 问题 3：消息显示但不完整

**症状**：
- 看到消息块，但内容是空的
- 或者只有部分内容

**检查**：
查看后端 `stream_thought` 方法是否正确发送了三个消息：
1. `is_start: true` - 开始
2. `is_stream: true, thought_content: "xxx"` - 内容（多次）
3. `is_end: true` - 结束

**解决**：
检查后端 `workflow_service.py` 的 `stream_thought` 方法。

## 📊 后端推送逻辑

### `workflow_service.py` 的 `stream_thought` 方法

```python
async def stream_thought(self, task_id: str, role: str, step: int, content: str):
    """流式推送 Agent 思考过程"""
    
    # 1. 发送开始消息
    await manager.broadcast(json.dumps({
        "is_stream": True,
        "is_start": True,
        "agent_role": role,
        "step_order": step,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }), str(task_id))
    
    # 2. 分块发送内容（每 5 个字符）
    chunk_size = 5
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i+chunk_size]
        await manager.broadcast(json.dumps({
            "is_stream": True,
            "agent_role": role,
            "thought_content": chunk,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }), str(task_id))
        await asyncio.sleep(0.05)  # 模拟打字效果
        
    # 3. 发送结束消息
    await manager.broadcast(json.dumps({
        "is_stream": True,
        "is_end": True,
        "agent_role": role,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }), str(task_id))
```

## ✅ 验证清单

- [ ] Python 后端运行在 `http://localhost:8000`
- [ ] 前端运行在 `http://localhost:5173`
- [ ] WebSocket 连接成功（绿色标签）
- [ ] 能看到 4 个 Agent 的发言
- [ ] 每个 Agent 的发言是流式显示的（逐字显示）
- [ ] 进度条正确更新（25%, 50%, 75%, 95%, 100%）
- [ ] 最终显示"查看最终报告"按钮
- [ ] 浏览器控制台没有错误

## 🎯 预期效果

**流式显示效果**：

```
[数据分析师] 正在分析商品历史数据...
              ↓ (0.05 秒后)
[数据分析师] 正在分析商品历史数据...分析完成
              ↓ (0.05 秒后)
[数据分析师] 正在分析商品历史数据...分析完成。建议折扣区间：8.5 折 -9 折
```

就像 AI 在逐字输入一样！

---

**修复时间**: 2026-03-17  
**修复版本**: v4.0  
**状态**: ✅ 已修复
