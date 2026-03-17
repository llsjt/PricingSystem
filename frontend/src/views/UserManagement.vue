<template>
  <div class="page-shell user-page">
    <section class="panel-card user-hero">
      <div class="section-title">
        <h2>用户管理</h2>
        <p>管理员可在这里集中维护系统账号，完成新增、修改和删除操作。</p>
      </div>
      <div class="metric-grid compact-metrics">
        <article class="metric-card">
          <div class="metric-label">用户总数</div>
          <div class="metric-value">{{ total }}</div>
          <div class="metric-hint">当前分页查询返回的总记录数</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">管理员账号</div>
          <div class="metric-value small">admin</div>
          <div class="metric-hint">系统保留账号，不允许删除</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">当前页容量</div>
          <div class="metric-value">{{ queryParams.size }}</div>
          <div class="metric-hint">支持快速切换分页尺寸</div>
        </article>
      </div>
    </section>

    <section class="panel-card table-card">
      <div class="section-head">
        <div class="section-title">
          <h3>账号列表</h3>
          <p>统一查看用户名、邮箱和创建时间，避免多级菜单跳转。</p>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" @click="openCreateDialog">新增用户</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column prop="createdAt" label="创建时间" min-width="180" />
        <el-table-column label="角色说明" min-width="140">
          <template #default="{ row }">
            <el-tag :type="row.username === 'admin' ? 'warning' : 'info'" effect="plain">
              {{ row.username === 'admin' ? '系统管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="170">
          <template #default="{ row }">
            <div class="inline-actions">
              <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm title="确认删除该用户吗？" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button link type="danger" :disabled="row.username === 'admin'">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchUsers"
          @current-change="fetchUsers"
        />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="isEditMode ? '编辑用户' : '新增用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="user-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEditMode && form.username === 'admin'" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="isEditMode ? '留空表示不修改密码' : '请输入登录密码'"
          />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱地址" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { addUser, deleteUser, getUserList, updateUser } from '../api/user'

const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const isEditMode = ref(false)
const editingUserId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const queryParams = reactive({
  page: 1,
  size: 10
})

const form = reactive({
  username: '',
  password: '',
  email: ''
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    {
      validator: (_rule, value, callback) => {
        if (!isEditMode.value && !value) {
          callback(new Error('请输入密码'))
          return
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

const resetForm = () => {
  form.username = ''
  form.password = ''
  form.email = ''
  editingUserId.value = null
  isEditMode.value = false
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const res: any = await getUserList(queryParams)
    if (res.code === 200) {
      tableData.value = res.data.records || []
      total.value = res.data.total || 0
      return
    }
    ElMessage.error(res.message || '获取用户列表失败')
  } catch {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (row: any) => {
  resetForm()
  dialogVisible.value = true
  isEditMode.value = true
  editingUserId.value = row.id
  form.username = row.username || ''
  form.email = row.email || ''
}

const submitUser = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      let res: any
      if (isEditMode.value && editingUserId.value !== null) {
        const payload: Record<string, string> = {
          username: form.username,
          email: form.email
        }
        if (form.password) {
          payload.password = form.password
        }
        res = await updateUser(editingUserId.value, payload)
      } else {
        res = await addUser({
          username: form.username,
          password: form.password,
          email: form.email
        })
      }

      if (res.code === 200) {
        ElMessage.success(isEditMode.value ? '用户已更新' : '用户已创建')
        dialogVisible.value = false
        resetForm()
        fetchUsers()
        return
      }
      ElMessage.error(res.message || '保存失败')
    } catch {
      ElMessage.error('保存失败')
    }
  })
}

const handleDelete = async (row: any) => {
  try {
    const res: any = await deleteUser(row.id)
    if (res.code === 200) {
      ElMessage.success('用户已删除')
      fetchUsers()
      return
    }
    ElMessage.error(res.message || '删除失败')
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.user-page {
  gap: 20px;
}

.compact-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.table-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.inline-actions {
  display: flex;
  gap: 8px;
}

.user-form {
  display: grid;
  gap: 8px;
}

@media (max-width: 1200px) {
  .compact-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .compact-metrics {
    grid-template-columns: 1fr;
  }

  .table-footer {
    justify-content: center;
  }
}
</style>
