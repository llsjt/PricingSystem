<template>
  <div class="page-shell shop-page">
    <section class="panel-card filter-panel">
      <div class="filter-head">
        <h3>店铺筛选</h3>
        <span>当前共 {{ filteredShops.length }} 家店铺</span>
      </div>

      <div class="toolbar-row filter-grid">
        <el-select v-model="filters.platform" clearable placeholder="店铺分类">
          <el-option label="全部分类" value="ALL" />
          <el-option
            v-for="platform in filterPlatformOptions"
            :key="platform"
            :label="platform"
            :value="platform"
          />
        </el-select>

        <div class="toolbar-actions">
          <el-button type="primary" @click="applyFilters">查询店铺</el-button>
          <el-button @click="resetFilters">重置条件</el-button>
        </div>
      </div>
    </section>

    <section class="panel-card table-card">
      <div class="section-head">
        <div class="section-title">
          <h3>店铺列表</h3>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" @click="openCreateDialog">新增店铺</el-button>
        </div>
      </div>

      <el-table :data="paginatedShops" v-loading="loading" border stripe class="shop-table">
        <el-table-column prop="shopName" label="店铺名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="platform" label="电商平台" width="120" />
        <el-table-column prop="sellerNick" label="卖家昵称" width="160" show-overflow-tooltip>
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

      <div class="table-footer">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="filteredShops.length"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageSizeChange"
        />
      </div>
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
// 店铺管理页：负责店铺的新增、编辑、删除与平台筛选。

import { computed, onMounted, reactive, ref, watch } from 'vue'
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
const appliedPlatformFilter = ref('ALL')
const filters = reactive({
  platform: 'ALL'
})
const queryParams = reactive({
  page: 1,
  size: 10
})

const form = ref<ShopCreateDTO>({ shopName: '', platform: '', sellerNick: '' })
const filterPlatformOptions = computed(() => {
  const fromList = shops.value
    .map((shop) => String(shop.platform || '').trim())
    .filter(Boolean)
  return Array.from(new Set([...platformOptions, ...fromList]))
})
const filteredShops = computed(() => {
  if (appliedPlatformFilter.value === 'ALL') {
    return shops.value
  }
  return shops.value.filter((shop) => String(shop.platform || '').trim() === appliedPlatformFilter.value)
})
const paginatedShops = computed(() => {
  const start = (queryParams.page - 1) * queryParams.size
  return filteredShops.value.slice(start, start + queryParams.size)
})

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

const applyFilters = () => {
  appliedPlatformFilter.value = filters.platform || 'ALL'
  queryParams.page = 1
}

const resetFilters = () => {
  filters.platform = 'ALL'
  appliedPlatformFilter.value = 'ALL'
  queryParams.page = 1
}

const handlePageSizeChange = () => {
  queryParams.page = 1
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

watch(
  () => filteredShops.value.length,
  (total) => {
    const maxPage = Math.max(Math.ceil(total / queryParams.size), 1)
    if (queryParams.page > maxPage) {
      queryParams.page = maxPage
    }
  },
  { immediate: true }
)

onMounted(() => fetchList())
</script>

<style scoped>
.shop-page {
  gap: 16px;
}

.filter-panel {
  padding: 10px 12px;
}

.filter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.filter-head h3 {
  margin: 0;
  font-size: 24px;
}

.filter-head span {
  color: var(--text-3);
  font-size: 12px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 220px auto;
  align-items: center;
  gap: 12px;
}

.filter-grid .toolbar-actions {
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.filter-panel :deep(.el-input__wrapper),
.filter-panel :deep(.el-select__wrapper) {
  min-height: 36px;
}

.table-card :deep(.el-table) {
  width: 100%;
}

.table-card :deep(.el-button.is-link) {
  font-weight: 600;
}

.table-footer {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-grid .toolbar-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
