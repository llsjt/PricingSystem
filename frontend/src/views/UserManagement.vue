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
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" effect="plain">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" min-width="180" />
        <el-table-column label="角色说明" min-width="140">
          <template #default="{ row }">
            <el-tag :type="row.role === 'ADMIN' ? 'warning' : 'info'" effect="plain">
              {{ row.role === 'ADMIN' ? '系统管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="170">
          <template #default="{ row }">
            <div class="inline-actions">
              <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm title="确认删除该用户吗？" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button link type="danger" :disabled="row.role === 'ADMIN'">删除</el-button>
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
          :layout="paginationLayout"
          @size-change="fetchUsers"
          @current-change="fetchUsers"
        />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="isEditMode ? '编辑用户' : '新增用户'" :width="dialogWidth">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="user-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEditMode && form.role === 'ADMIN'" />
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
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" :disabled="isEditMode && form.role === 'ADMIN'">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" :disabled="isEditMode && form.role === 'ADMIN'">
            <el-option label="普通用户" value="USER" />
            <el-option label="管理员" value="ADMIN" />
          </el-select>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { addUser, batchDeleteUsers, deleteUser, getUserList, updateUser, type UserListItem, type UserPayload } from '../api/user'
import { useViewport } from '../composables/useViewport'
import { resolveRequestErrorMessage } from '../utils/error'

interface UserFormModel {
  username: string
  password: string
  email: string
  status: number
  role: string
}

const { isMobile } = useViewport()

const dialogWidth = computed(() => (isMobile.value ? '90%' : '520px'))
const paginationLayout = computed(() =>
  isMobile.value ? 'total, prev, next' : 'total, sizes, prev, pager, next, jumper'
)

const loading = ref(false)
const tableData = ref<UserListItem[]>([])
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

const createDefaultForm = (): UserFormModel => ({
  username: '',
  password: '',
  email: '',
  status: 1,
  role: 'USER'
})

const form = reactive(createDefaultForm())

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
  Object.assign(form, createDefaultForm())
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
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '获取用户列表失败'))
  } finally {
    loading.value = false
  }
}

const isRowSelectable = (row: UserListItem) => row.role !== 'ADMIN'

const handleSelectionChange = (rows: UserListItem[]) => {
  selectedIds.value = rows.map((row) => Number(row.id)).filter((id) => Number.isFinite(id))
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (row: UserListItem) => {
  resetForm()
  dialogVisible.value = true
  isEditMode.value = true
  editingUserId.value = row.id
  form.username = row.username || ''
  form.email = row.email || ''
  form.status = row.status ?? 1
  form.role = row.role || 'USER'
}

const buildUpdatePayload = (): UserPayload => {
  const payload: UserPayload = {
    username: form.username,
    email: form.email,
    status: form.status,
    role: form.role
  }
  if (form.password) {
    payload.password = form.password
  }
  return payload
}

const buildCreatePayload = (): UserPayload => ({
  username: form.username,
  password: form.password,
  email: form.email,
  status: form.status,
  role: form.role
})

const submitUser = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      const res: any = isEditMode.value && editingUserId.value !== null
        ? await updateUser(editingUserId.value, buildUpdatePayload())
        : await addUser(buildCreatePayload())

      if (res.code === 200) {
        ElMessage.success(isEditMode.value ? '用户已更新' : '用户已创建')
        dialogVisible.value = false
        resetForm()
        await fetchUsers()
        return
      }
      ElMessage.error(res.message || '保存失败')
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '保存失败'))
    }
  })
}

const handleDelete = async (row: UserListItem) => {
  try {
    const res: any = await deleteUser(row.id)
    if (res.code === 200) {
      ElMessage.success('用户已删除')
      await fetchUsers()
      return
    }
    ElMessage.error(res.message || '删除失败')
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '删除失败'))
  }
}

const confirmBatchDelete = async () => {
  await ElMessageBox.confirm(
    '确定删除已选择的 ' + selectedIds.value.length + ' 个用户吗？此操作不可恢复。',
    '批量删除确认',
    {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消'
    }
  )
}

const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的用户')
    return
  }

  try {
    await confirmBatchDelete()
  } catch {
    return
  }

  try {
    const res: any = await batchDeleteUsers(selectedIds.value)
    if (res.code === 200) {
      ElMessage.success('批量删除成功')
      await fetchUsers()
      return
    }
    ElMessage.error(res.message || '批量删除失败')
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '批量删除失败'))
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
  justify-content: center;
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

  :deep(.el-table) {
    font-size: 13px;
  }

  .table-footer :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: center;
  }
}
</style>
