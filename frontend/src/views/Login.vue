<!-- 登录页，处理账号登录、令牌落库与登录失败提示。 -->

<template>
  <div class="login-container">
    <div class="login-wrapper">
      <!-- 左侧用于展示系统定位、能力亮点和品牌信息。 -->
      <div class="info-section">
        <div class="info-content">
          <div class="brand-logo">
            <el-icon :size="28"><DataLine /></el-icon>
            <span>Pricing AI</span>
          </div>
          <h1 class="main-title">电商智能定价<br>决策中枢</h1>
          <p class="sub-title">基于多智能体（Multi-Agent）架构的自动化定价系统</p>
          
          <div class="feature-list">
            <div class="feature-item">
              <div class="feature-icon-wrapper">
                <el-icon><Goods /></el-icon>
              </div>
              <div class="feature-text">
                <h3>基础数据与商品管理</h3>
                <p>统一管理店铺及商品信息，支持快捷导入历史经营、流量指标数据</p>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon-wrapper">
                <el-icon><Cpu /></el-icon>
              </div>
              <div class="feature-text">
                <h3>多智能体定价实验室</h3>
                <p>融合数据分析、竞品收集与风控智能体，动态生成商品调价策略</p>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon-wrapper">
                <el-icon><Document /></el-icon>
              </div>
              <div class="feature-text">
                <h3>决策日志与结果归档</h3>
                <p>实时追踪 Agent 分析链路，人工审核确认报价并支持历史结果追溯</p>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 装饰性背景元素，只承担视觉氛围，不参与交互。 -->
        <div class="decoration circle-1"></div>
        <div class="decoration circle-2"></div>
      </div>

      <!-- 右侧为登录表单区域，负责账号输入和登录提交。 -->
      <div class="form-section">
        <div class="form-wrapper">
          <div class="form-header">
            <h2>欢迎回来</h2>
            <p>登录您的账号以进入控制台</p>
          </div>

          <el-form ref="loginFormRef" :model="loginForm" :rules="rules" label-position="top">
            <el-form-item prop="username" label="用户名">
              <el-input 
                v-model="loginForm.username" 
                placeholder="请输入您的用户名" 
                size="large"
                :prefix-icon="User"
              />
            </el-form-item>
            <el-form-item prop="password" label="密码">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入您的密码"
                size="large"
                show-password
                :prefix-icon="Lock"
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            
            <div class="form-options">
              <el-checkbox v-model="rememberMe">记住密码</el-checkbox>
              <a href="javascript:void(0)" class="forgot-pwd" @click="handleForgotPwd">遇到问题？</a>
            </div>

            <el-form-item>
              <el-button 
                type="primary" 
                :loading="loading" 
                size="large"
                class="login-submit-btn"
                @click="handleLogin"
              >
                立即登录
              </el-button>
            </el-form-item>
          </el-form>

          <div class="tips">
            <span>演示默认账号：</span>
            <span class="highlight">Use an assigned account</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { DataLine, TrendCharts, Connection, Warning, User, Lock, Goods, Cpu, Document } from '@element-plus/icons-vue'
import { login } from '../api/user'
import { useUserStore } from '../stores/user'
import { useShopStore } from '../stores/shop'
import { clearAuthSession } from '../utils/authSession'
import { resolveRequestErrorMessage, toUserFacingErrorMessage } from '../utils/error'

const router = useRouter()
const userStore = useUserStore()
const shopStore = useShopStore()

// 进入登录页时清除旧的认证状态，避免残留 token 导致后台请求产生 401/403 错误
onMounted(() => {
  clearAuthSession()
  userStore.clearSession()
})
const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const rememberMe = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 登录成功后统一刷新店铺状态并跳转首页；失败时尽量把接口异常转成可读提示。
const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    loading.value = true
    try {
      const res: any = await login(loginForm)
      if (res.code === 200) {
        shopStore.resetState()
        userStore.applySession({
          token: res.data.token,
          username: res.data.username,
          role: res.data.role,
          isAdmin: Boolean(res.data.isAdmin)
        })
        ElMessage.success('登录成功')
        router.push('/')
      } else {
        ElMessage.error(toUserFacingErrorMessage(res.message, '登录失败，请检查用户名或密码'))
      }
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '登录失败，请检查用户名或密码'))
    } finally {
      loading.value = false
    }
  })
}

const handleForgotPwd = () => {
  ElMessage.info('请联系系统管理员获取访问权限')
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  width: 100vw;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f0f2f5;
  font-family: 'Inter', 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
  overflow: hidden;
}

.login-wrapper {
  display: flex;
  width: 1000px;
  height: auto;
  min-height: 540px;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* 左侧品牌与项目信息区域 */
.info-section {
  flex: 1;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #fff;
  padding: 50px 40px;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.info-content {
  position: relative;
  z-index: 2;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 40px;
  color: #60a5fa;
  letter-spacing: 1px;
}

.main-title {
  font-size: 36px;
  font-weight: 600;
  line-height: 1.3;
  margin: 0 0 16px 0;
  background: linear-gradient(to right, #ffffff, #93c5fd);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sub-title {
  font-size: 15px;
  color: #94a3b8;
  margin-bottom: 40px;
  line-height: 1.6;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.feature-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  font-size: 20px;
  flex-shrink: 0;
}

.feature-text h3 {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 6px 0;
  color: #e2e8f0;
}

.feature-text p {
  font-size: 13px;
  color: #94a3b8;
  margin: 0;
  line-height: 1.5;
}

/* 装饰性背景圆形 */
.decoration {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  z-index: 0;
}

.circle-1 {
  width: 300px;
  height: 300px;
  background: rgba(59, 130, 246, 0.2);
  top: -100px;
  left: -100px;
}

.circle-2 {
  width: 250px;
  height: 250px;
  background: rgba(139, 92, 246, 0.15);
  bottom: -50px;
  right: -50px;
}

/* 右侧登录表单区域 */
.form-section {
  width: 440px;
  padding: 50px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #ffffff;
}

.form-wrapper {
  width: 100%;
}

.form-header {
  margin-bottom: 30px;
}

.form-header h2 {
  font-size: 26px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px 0;
}

.form-header p {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #334155;
  padding-bottom: 6px;
}

:deep(.el-input__wrapper) {
  background-color: #f8fafc;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  border-radius: 8px;
  transition: all 0.3s;
}

:deep(.el-input__wrapper:hover), :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #3b82f6 inset;
  background-color: #ffffff;
}

:deep(.el-input__inner) {
  color: #1e293b;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  margin-top: -8px;
}

.forgot-pwd {
  font-size: 13px;
  color: #3b82f6;
  text-decoration: none;
  transition: color 0.3s;
}

.forgot-pwd:hover {
  color: #2563eb;
}

.login-submit-btn {
  width: 100%;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  height: 44px;
  background: #3b82f6;
  border: none;
  transition: all 0.3s;
}

.login-submit-btn:hover {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.tips {
  margin-top: 24px;
  font-size: 13px;
  color: #64748b;
  text-align: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
}

.tips .highlight {
  color: #3b82f6;
  font-weight: 600;
  margin-left: 4px;
}

/* 小屏幕下切换为上下布局，避免品牌区和表单区挤压 */
@media screen and (max-width: 800px) {
  .login-wrapper {
    width: 90%;
    flex-direction: column;
    min-height: 600px;
  }
  
  .info-section {
    padding: 40px 30px;
    flex: none;
  }
  
  .form-section {
    width: 100%;
    padding: 40px 30px;
  }
}
</style>
