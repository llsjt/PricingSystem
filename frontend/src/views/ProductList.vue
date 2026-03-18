<template>
  <div class="page-shell">
    <section class="panel-card table-card product-card">
      <div class="section-head">
        <div class="section-title">
          <h3>商品列表</h3>
          <p>支持搜索、新增和批量删除。</p>
        </div>
        <div class="toolbar-actions">
          <el-button @click="handleSearch">刷新</el-button>
          <el-button type="success" @click="openAddDialog">新增商品</el-button>
          <el-button type="danger" :disabled="selectedIds.length === 0" @click="handleBatchDelete">
            批量删除
          </el-button>
        </div>
      </div>

      <div class="toolbar-row grow search-toolbar">
        <el-input
          v-model="queryParams.keyword"
          clearable
          placeholder="搜索商品标题或 ID"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="queryParams.dataSource" clearable placeholder="数据来源">
          <el-option label="全部来源" value="" />
          <el-option label="导入" value="IMPORT" />
          <el-option label="手工录入" value="MANUAL" />
        </el-select>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
      </div>

      <div class="selected-bar" v-if="selectedIds.length > 0">
        <el-tag type="success">已选择 {{ selectedIds.length }} 个商品</el-tag>
      </div>

      <div class="table-scroll">
        <el-table
          :data="tableData"
          border
          stripe
          v-loading="loading"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="52" />
          <el-table-column prop="id" label="ID" width="82" sortable />
          <el-table-column prop="title" label="商品标题" min-width="220" show-overflow-tooltip />
          <el-table-column prop="category" label="类别" min-width="110" />
          <el-table-column prop="source" label="来源" width="110">
            <template #default="{ row }">
              <el-tag :type="row.source === 'IMPORT' ? 'info' : 'warning'">
                {{ row.source === 'IMPORT' ? '导入' : '手工' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="costPrice" label="成本价" min-width="110" sortable>
            <template #default="{ row }">¥{{ Number(row.costPrice || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="currentPrice" label="当前售价" min-width="110" sortable>
            <template #default="{ row }">¥{{ Number(row.currentPrice || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="stock" label="库存" width="88" sortable />
          <el-table-column prop="monthlySales" label="月销量" width="96" sortable />
          <el-table-column label="操作" fixed="right" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openTrendDrawer(row)">查看趋势</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="isMobile ? '新增商品' : '新增商品（手工录入）'"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" class="product-form">
        <div class="form-grid">
          <el-form-item label="商品标题" prop="title">
            <el-input v-model="form.title" placeholder="请输入商品标题" />
          </el-form-item>
          <el-form-item label="商品类别" prop="category">
            <el-input v-model="form.category" placeholder="请输入商品类别" />
          </el-form-item>
          <el-form-item label="成本价" prop="costPrice">
            <el-input-number v-model="form.costPrice" :min="0" :precision="2" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="市场价" prop="marketPrice">
            <el-input-number v-model="form.marketPrice" :min="0" :precision="2" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="当前售价" prop="currentPrice">
            <el-input-number v-model="form.currentPrice" :min="0" :precision="2" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="库存" prop="stock">
            <el-input-number v-model="form.stock" :min="0" :precision="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="月销量" prop="monthlySales">
            <el-input-number v-model="form.monthlySales" :min="0" :precision="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="点击率" prop="clickRate">
            <el-input-number v-model="form.clickRate" :min="0" :max="1" :precision="4" :step="0.0001" style="width: 100%" />
          </el-form-item>
          <el-form-item label="转化率" prop="conversionRate">
            <el-input-number v-model="form.conversionRate" :min="0" :max="1" :precision="4" :step="0.0001" style="width: 100%" />
          </el-form-item>
        </div>
        <div class="mini-note">点击率和转化率请输入 0 到 1 之间的小数，例如 `0.05` 表示 5%。</div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProduct">保存商品</el-button>
      </template>
    </el-dialog>

    <ProductTrendDrawer ref="trendDrawerRef" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { addProductManual, batchDeleteProducts, getProductList } from '../api/product'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import ProductTrendDrawer from '../components/ProductTrendDrawer.vue'

const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const selectedIds = ref<number[]>([])
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const trendDrawerRef = ref<InstanceType<typeof ProductTrendDrawer>>()

const queryParams = reactive({
  page: 1,
  size: 10,
  keyword: '',
  dataSource: ''
})

const form = reactive({
  title: '',
  category: '',
  costPrice: 0,
  marketPrice: 0,
  currentPrice: 0,
  stock: 0,
  monthlySales: 0,
  clickRate: 0,
  conversionRate: 0,
  source: 'MANUAL'
})

const rules = {
  title: [{ required: true, message: '请输入商品标题', trigger: 'blur' }],
  costPrice: [{ required: true, message: '请输入成本价', trigger: 'blur' }],
  currentPrice: [{ required: true, message: '请输入当前售价', trigger: 'blur' }]
}

const isMobile = computed(() => window.innerWidth <= 768)

const resetForm = () => {
  form.title = ''
  form.category = ''
  form.costPrice = 0
  form.marketPrice = 0
  form.currentPrice = 0
  form.stock = 0
  form.monthlySales = 0
  form.clickRate = 0
  form.conversionRate = 0
}

const handleSearch = async () => {
  loading.value = true
  try {
    const res: any = await getProductList(queryParams)
    if (res?.code === 200) {
      tableData.value = res.data.records || []
      total.value = res.data.total || 0
      return
    }
    ElMessage.error(res?.message || '加载商品失败')
  } catch {
    ElMessage.error('网络异常，无法加载商品')
  } finally {
    loading.value = false
  }
}

const refreshList = () => {
  queryParams.page = 1
  handleSearch()
}

defineExpose({ refreshList })

const handleSelectionChange = (selection: any[]) => {
  selectedIds.value = selection.map((item) => item.id)
}

const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的商品')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除已选择的 ${selectedIds.value.length} 个商品吗？此操作不可恢复。`,
      '批量删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    loading.value = true
    const res: any = await batchDeleteProducts(selectedIds.value)
    if (res?.code === 200) {
      selectedIds.value = []
      ElMessage.success('批量删除成功')
      handleSearch()
      return
    }
    ElMessage.error(res?.message || '批量删除失败')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  } finally {
    loading.value = false
  }
}

const openAddDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const submitProduct = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      const res: any = await addProductManual(form)
      if (res?.code === 200) {
        ElMessage.success('商品新增成功')
        dialogVisible.value = false
        handleSearch()
        return
      }
      ElMessage.error(res?.message || '商品新增失败')
    } catch {
      ElMessage.error('提交失败，请稍后重试')
    }
  })
}

const openTrendDrawer = (row: any) => {
  trendDrawerRef.value?.open(row)
}

onMounted(() => {
  handleSearch()
})
</script>

<style scoped>
.product-card {
  padding: 20px;
}

.search-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 460px) 220px 132px;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.search-toolbar :deep(.el-button) {
  width: 132px;
  justify-self: start;
}

.selected-bar {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
}

.table-scroll {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
}

.product-form {
  display: grid;
  gap: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

@media (max-width: 768px) {
  .product-card {
    padding: 16px;
  }

  .search-toolbar {
    grid-template-columns: 1fr;
  }

  .search-toolbar :deep(.el-button) {
    width: 100%;
    justify-self: stretch;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
