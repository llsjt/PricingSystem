<template>
  <div class="page-shell user-page">
    <section class="panel-card table-card">
      <div class="section-head">
        <div class="section-title">
          <h3>账号列表</h3>
          <p>支持新增、编辑、单个删除和批量删除。</p>
        </div>
        <div class="toolbar-actions">
          <el-button type="danger" :disabled="selectedIds.length === 0" @click="handleBatchDelete">
            批量删除
          </el-button>
          <el-button type="primary" @click="openCreateDialog">新增用户</el-button>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="tableData"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="52" :selectable="isRowSelectable" />
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

      <div v-if="selectedIds.length > 0" class="selected-bar">已选择 {{ selectedIds.length }} 个用户</div>

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
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { addUser, batchDeleteUsers, deleteUser, getUserList, updateUser } from '../api/user'

const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const isEditMode = ref(false)
const editingUserId = ref<number | null>(null)
const selectedIds = ref<number[]>([])
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
      selectedIds.value = []
      return
    }
    ElMessage.error(res.message || '获取用户列表失败')
  } catch {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const isRowSelectable = (row: any) => row.username !== 'admin'

const handleSelectionChange = (rows: any[]) => {
  selectedIds.value = rows.map((row) => Number(row.id)).filter((id) => Number.isFinite(id))
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

const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的用户')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除已选择的 ${selectedIds.value.length} 个用户吗？此操作不可恢复。`,
      '批量删除确认',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }

  try {
    const res: any = await batchDeleteUsers(selectedIds.value)
    if (res.code === 200) {
      ElMessage.success('批量删除成功')
      fetchUsers()
      return
    }
    ElMessage.error(res.message || '批量删除失败')
  } catch {
    ElMessage.error('批量删除失败')
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

.toolbar-actions {
  display: flex;
  gap: 10px;
}

.selected-bar {
  margin-top: 12px;
  color: var(--el-color-success);
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

@media (max-width: 768px) {
  .toolbar-actions {
    flex-wrap: wrap;
  }

  .table-footer {
    justify-content: center;
  }
}
</style>
