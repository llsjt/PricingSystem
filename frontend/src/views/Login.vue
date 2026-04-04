<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="header">
          <h2>智能定价决策系统</h2>
        </div>
      </template>

      <el-form ref="loginFormRef" :model="loginForm" :rules="rules" label-width="0">
        <el-form-item prop="username" class="field-item">
          <div class="field-label">用户名</div>
          <el-input v-model="loginForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item prop="password" class="field-item">
          <div class="field-label">密码</div>
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width: 100%" @click="handleLogin">登录</el-button>
        </el-form-item>
      </el-form>

      <div class="tips">默认管理员：admin / 123456</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { login } from '../api/user'
import { useUserStore } from '../stores/user'
import { useShopStore } from '../stores/shop'
import { resolveRequestErrorMessage } from '../utils/error'

const router = useRouter()
const userStore = useUserStore()
const shopStore = useShopStore()
const loginFormRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) {
    return
  }

  await loginFormRef.value.validate(async (valid: boolean) => {
    if (!valid) {
      return
    }

    loading.value = true
    try {
      const res: any = await login(loginForm)
      if (res.code === 200) {
        shopStore.resetState()
        userStore.applySession({
          token: res.data.token,
          username: res.data.username,
          isAdmin: Boolean(res.data.isAdmin)
        })
        ElMessage.success('登录成功')
        router.push('/')
      } else {
        ElMessage.error(res.message || '登录失败')
      }
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '登录失败'))
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #2d3a4b;
}

.login-card {
  width: 90%;
  max-width: 400px;
  min-width: 280px;
}

.header {
  text-align: center;
}

.field-item :deep(.el-form-item__content) {
  display: block;
}

.field-label {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: #25364d;
}

.tips {
  margin-top: 10px;
  font-size: 12px;
  color: #999;
  text-align: center;
}
</style>
