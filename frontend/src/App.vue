<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView />
</template>

<style>
:root {
  color-scheme: light;
  --app-bg: #eff5ff;
  --surface-1: #ffffff;
  --surface-2: #f7faff;
  --surface-3: #edf4ff;
  --panel-muted: #f4f8ff;
  --line-soft: rgba(31, 46, 77, 0.08);
  --line-strong: rgba(31, 46, 77, 0.14);
  --border-soft: rgba(31, 46, 77, 0.08);
  --text-1: #17233a;
  --text-2: #52627a;
  --text-3: #8091a7;
  --text-primary: var(--text-1);
  --text-secondary: var(--text-2);
  --text-tertiary: var(--text-3);
  --brand: #1f6feb;
  --brand-strong: #1558b5;
  --brand-soft: rgba(31, 111, 235, 0.12);
  --accent: #ff9f43;
  --danger-soft: rgba(214, 82, 82, 0.14);
  --success-soft: rgba(47, 161, 116, 0.14);
  --warning-soft: rgba(255, 159, 67, 0.14);
  --shadow-soft: 0 18px 48px rgba(17, 35, 43, 0.08);
  --shadow-card: 0 10px 24px rgba(17, 35, 43, 0.06);
  --radius-xl: 28px;
  --radius-lg: 22px;
  --radius-md: 16px;
  --radius-sm: 12px;
  --content-width: 1380px;
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body,
#app {
  min-height: 100%;
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
}

body {
  margin: 0;
  overflow-x: hidden;
  background:
    radial-gradient(circle at top left, rgba(31, 111, 235, 0.12), transparent 28%),
    radial-gradient(circle at right 16%, rgba(255, 159, 67, 0.14), transparent 24%),
    linear-gradient(180deg, #f8fbff 0%, var(--app-bg) 100%);
  color: var(--text-1);
}

a {
  color: inherit;
}

.page-shell,
.responsive-two,
.responsive-three,
.toolbar-row,
.section-head,
.panel-card {
  min-width: 0;
  width: 100%;
  max-width: 100%;
}

.page-shell {
  display: grid;
  gap: 20px;
}

.panel-card {
  padding: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 255, 0.96));
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.section-title h2,
.section-title h3,
.section-title h4,
.section-title p {
  margin: 0;
}

.section-title h2,
.section-title h3 {
  font-size: 24px;
  line-height: 1.2;
  color: var(--text-1);
}

.section-title p {
  color: var(--text-2);
  font-size: 14px;
}

.panel-card .section-title p {
  display: none;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  width: 100%;
  min-width: 0;
}

.metric-card {
  position: relative;
  overflow: hidden;
  padding: 20px 22px;
  border-radius: var(--radius-md);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98), rgba(240, 246, 255, 0.96));
  border: 1px solid rgba(31, 111, 235, 0.10);
}

.metric-card::before {
  content: "";
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, var(--brand), var(--accent));
  opacity: 0.9;
}

.metric-card::after {
  content: "";
  position: absolute;
  inset: auto -20px -30px auto;
  width: 110px;
  height: 110px;
  border-radius: 999px;
  background: rgba(31, 111, 235, 0.10);
}

.metric-label {
  position: relative;
  z-index: 1;
  color: var(--text-2);
  font-size: 13px;
}

.metric-value {
  position: relative;
  z-index: 1;
  margin-top: 10px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.03em;
}

.metric-hint {
  position: relative;
  z-index: 1;
  margin-top: 8px;
  color: var(--text-3);
  font-size: 12px;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.toolbar-row.grow > * {
  flex: 1 1 180px;
  min-width: 0;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.table-card {
  padding: 20px;
  overflow: hidden;
}

.table-card .el-table {
  --el-table-border-color: rgba(31, 46, 77, 0.08);
  --el-table-header-bg-color: #f5f8ff;
  --el-table-row-hover-bg-color: rgba(31, 111, 235, 0.05);
  border-radius: 16px;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}

.table-card .el-table th {
  color: var(--text-2);
  font-weight: 600;
}

.table-card :deep(.el-table__inner-wrapper),
.table-card :deep(.el-scrollbar),
.table-card :deep(.el-scrollbar__wrap) {
  max-width: 100%;
}

.table-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.mini-note {
  color: var(--text-3);
  font-size: 12px;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.responsive-two {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 0.95fr);
  gap: 18px;
}

.responsive-three {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.el-button--primary {
  --el-button-bg-color: var(--brand);
  --el-button-border-color: var(--brand);
  --el-button-hover-bg-color: var(--brand-strong);
  --el-button-hover-border-color: var(--brand-strong);
  --el-button-active-bg-color: var(--brand-strong);
  --el-button-active-border-color: var(--brand-strong);
}

.el-button--success {
  --el-button-bg-color: #16a34a;
  --el-button-border-color: #16a34a;
  --el-button-hover-bg-color: #15803d;
  --el-button-hover-border-color: #15803d;
}

.el-button--danger {
  --el-button-bg-color: #dc2626;
  --el-button-border-color: #dc2626;
  --el-button-hover-bg-color: #b91c1c;
  --el-button-hover-border-color: #b91c1c;
}

.el-button.is-link {
  font-weight: 600;
}

.el-input__wrapper,
.el-textarea__inner,
.el-select__wrapper,
.el-input-number,
.el-date-editor.el-input__wrapper {
  border-radius: 14px;
}

.el-card {
  border-radius: var(--radius-lg);
  border-color: var(--line-soft);
  box-shadow: var(--shadow-card);
}

.el-tabs__item {
  font-weight: 600;
}

.el-dialog,
.el-drawer {
  border-radius: 24px 24px 0 0;
}

.el-tag {
  border-radius: 999px;
  padding-inline: 10px;
}

@media (max-width: 1200px) {
  .metric-grid,
  .responsive-three {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .responsive-two {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .metric-grid,
  .responsive-three {
    grid-template-columns: 1fr;
  }

  .section-title h2,
  .section-title h3 {
    font-size: 20px;
  }

  .panel-card,
  .table-card {
    padding: 16px;
  }

  .table-footer {
    justify-content: center;
  }

  .el-dialog {
    width: calc(100vw - 24px) !important;
    margin-top: 4vh !important;
  }
}
</style>
