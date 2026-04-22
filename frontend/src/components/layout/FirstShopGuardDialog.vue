<script setup lang="ts">
import type { ShopCreateDTO } from '../../api/shop'

defineProps<{
  loading: boolean
  modelValue: boolean
  shopForm: ShopCreateDTO
}>()

const emit = defineEmits<{
  submit: []
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="欢迎！请先创建您的第一个店铺"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    width="480px"
  >
    <el-form :model="shopForm" label-width="80px">
      <el-form-item label="店铺名称" required>
        <el-input v-model="shopForm.shopName" placeholder="如：我的淘宝店" />
      </el-form-item>
      <el-form-item label="电商平台" required>
        <el-select v-model="shopForm.platform" placeholder="请选择" style="width: 100%">
          <el-option v-for="p in ['淘宝', '天猫', '京东', '拼多多', '抖音']" :key="p" :label="p" :value="p" />
        </el-select>
      </el-form-item>
      <el-form-item label="卖家昵称">
        <el-input v-model="shopForm.sellerNick" placeholder="选填" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="loading" @click="emit('submit')">创建店铺</el-button>
    </template>
  </el-dialog>
</template>
