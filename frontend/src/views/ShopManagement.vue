<template>
  <div class="page-shell">
    <section class="panel-card">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">店铺管理</h2>
        </div>
        <el-button type="primary" @click="openCreateDialog">新增店铺</el-button>
      </div>

      <el-table :data="shops" v-loading="loading" stripe class="shop-table">
        <el-table-column prop="shopName" label="店铺名称" min-width="160" />
        <el-table-column prop="platform" label="电商平台" width="120" />
        <el-table-column prop="sellerNick" label="卖家昵称" width="140">
          <template #default="{ row }">{{ row.sellerNick || '-' }}</template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑店铺' : '新增店铺'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="店铺名称" required>
          <el-input v-model="form.shopName" placeholder="如：我的淘宝店" />
        </el-form-item>
        <el-form-item label="电商平台" required>
          <el-select v-model="form.platform" placeholder="请选择" style="width: 100%">
            <el-option v-for="p in platformOptions" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="卖家昵称">
          <el-input v-model="form.sellerNick" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createShop, deleteShop, updateShop, type Shop, type ShopCreateDTO } from '../api/shop'
import { useShopStore } from '../stores/shop'
import { resolveRequestErrorMessage } from '../utils/error'

const shopStore = useShopStore()
const shops = ref<Shop[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const platformOptions = ['淘宝', '天猫', '京东', '拼多多', '抖音']

const form = ref<ShopCreateDTO>({ shopName: '', platform: '', sellerNick: '' })

const fetchList = async (force = false) => {
  loading.value = true
  try {
    await shopStore.fetchShops(force)
    shops.value = shopStore.shops
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEdit.value = false
  editingId.value = null
  form.value = { shopName: '', platform: '', sellerNick: '' }
  dialogVisible.value = true
}

const openEditDialog = (row: Shop) => {
  isEdit.value = true
  editingId.value = row.id
  form.value = { shopName: row.shopName, platform: row.platform, sellerNick: row.sellerNick }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.value.shopName.trim()) {
    ElMessage.warning('请输入店铺名称')
    return
  }
  if (!form.value.platform) {
    ElMessage.warning('请选择电商平台')
    return
  }

  submitting.value = true
  try {
    if (isEdit.value && editingId.value) {
      const res: any = await updateShop(editingId.value, form.value)
      if (res.code === 200) {
        ElMessage.success('更新成功')
      } else {
        ElMessage.error(res.message || '更新失败')
        return
      }
    } else {
      const res: any = await createShop(form.value)
      if (res.code === 200) {
        ElMessage.success('创建成功')
      } else {
        ElMessage.error(res.message || '创建失败')
        return
      }
    }
    dialogVisible.value = false
    await fetchList(true)
  } catch (error) {
    const message = await resolveRequestErrorMessage(error)
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row: Shop) => {
  try {
    await ElMessageBox.confirm(`确定删除店铺"${row.shopName}"吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res: any = await deleteShop(row.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      await fetchList(true)
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      const message = await resolveRequestErrorMessage(error)
      ElMessage.error(message)
    }
  }
}

onMounted(() => fetchList())
</script>

<style scoped>
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.panel-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #24324a;
}

.shop-table {
  width: 100%;
}
</style>
