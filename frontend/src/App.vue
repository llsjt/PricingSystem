<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView />
</template>

<style>
:root {
  color-scheme: light;
  --app-bg: #eef4fc;
  --surface-1: #ffffff;
  --surface-2: #f6f9fe;
  --surface-3: #edf3fc;
  --panel-muted: #f3f8ff;
  --line-soft: rgba(31, 46, 77, 0.08);
  --line-strong: rgba(31, 46, 77, 0.14);
  --border-soft: rgba(31, 46, 77, 0.08);
  --border-active: rgba(31, 111, 235, 0.22);
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
  --shadow-soft: 0 18px 44px rgba(22, 39, 58, 0.1);
  --shadow-card: 0 10px 28px rgba(20, 40, 63, 0.08);
  --radius-xl: 20px;
  --radius-lg: 16px;
  --radius-md: 14px;
  --radius-sm: 12px;
  --motion-fast: 0.2s ease-in-out;
  --content-width: 1460px;
  --panel-padding: 20px;
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
    radial-gradient(circle at top left, rgba(58, 118, 196, 0.12), transparent 30%),
    radial-gradient(circle at right 14%, rgba(152, 187, 227, 0.15), transparent 26%),
    linear-gradient(180deg, #f9fcff 0%, var(--app-bg) 100%);
  color: var(--text-1);
}

a {
  color: inherit;
}

button,
[role="button"] {
  cursor: pointer;
}

:focus-visible {
  outline: 2px solid rgba(31, 111, 235, 0.36);
  outline-offset: 2px;
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
  gap: 16px;
}

.panel-card {
  padding: var(--panel-padding);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(249, 252, 255, 0.98));
  border: 1px solid rgba(31, 46, 77, 0.07);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: border-color var(--motion-fast), background var(--motion-fast);
}

.panel-card:hover {
  border-color: rgba(31, 46, 77, 0.07);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.section-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.section-title h1,
.section-title h2,
.section-title h3,
.section-title h4,
.section-title p {
  margin: 0;
}

.section-title h1 {
  font-size: 30px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-1);
}

.section-title h2,
.section-title h3 {
  font-size: 24px;
  line-height: 1.2;
  color: var(--text-1);
}

.section-title h4 {
  font-size: 16px;
  line-height: 1.35;
  color: var(--text-1);
}

.section-title p {
  color: var(--text-2);
  font-size: 13px;
  line-height: 1.55;
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
  padding: 18px 20px;
  border-radius: var(--radius-md);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.96));
  border: 1px solid rgba(31, 46, 77, 0.08);
  box-shadow: none;
  transition: border-color var(--motion-fast), background var(--motion-fast);
}

.metric-card::before {
  display: none;
}

.metric-card:hover {
  border-color: rgba(31, 46, 77, 0.08);
}

.metric-label {
  position: relative;
  z-index: 1;
  color: var(--text-2);
  font-size: 13px;
  font-weight: 600;
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
  margin-top: 10px;
  color: var(--text-3);
  font-size: 12px;
  line-height: 1.5;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.toolbar-row.grow > * {
  flex: 1 1 180px;
  min-width: 0;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-card {
  padding: var(--panel-padding);
  overflow: hidden;
}

.table-card .el-table {
  --el-table-border-color: rgba(31, 46, 77, 0.08);
  --el-table-header-bg-color: #f5f8ff;
  --el-table-row-hover-bg-color: rgba(31, 111, 235, 0.05);
  border-radius: 10px;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}

.table-card .el-table th {
  color: var(--text-2);
  font-weight: 600;
}

.table-card :deep(.el-table th),
.table-card :deep(.el-table td) {
  padding: 12px 0;
}

.table-card :deep(.el-table__inner-wrapper),
.table-card :deep(.el-scrollbar),
.table-card :deep(.el-scrollbar__wrap) {
  max-width: 100%;
}

.table-footer {
  display: flex;
  justify-content: center;
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
  gap: 16px;
}

.responsive-three {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.el-button,
.el-input__wrapper,
.el-select__wrapper,
.el-textarea__inner {
  transition: all var(--motion-fast);
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

.el-button:hover,
.el-button:focus-visible,
.el-tabs__item:hover,
.el-tag:hover {
  transform: translateY(-1px);
}

.el-input__wrapper,
.el-textarea__inner,
.el-select__wrapper,
.el-input-number,
.el-date-editor.el-input__wrapper {
  border-radius: 12px;
}

.el-input__wrapper:hover,
.el-select__wrapper:hover,
.el-date-editor.el-input__wrapper:hover,
.el-input-number:hover {
  box-shadow: 0 0 0 1px rgba(31, 111, 235, 0.14);
}

.el-input__wrapper.is-focus,
.el-select__wrapper.is-focused,
.el-date-editor.el-input__wrapper.is-focus,
.el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--border-active) !important;
}

.el-card {
  border-radius: var(--radius-lg);
  border-color: var(--line-soft);
  box-shadow: var(--shadow-card);
}

.el-tabs__item {
  font-weight: 600;
}

.el-empty__description p {
  color: var(--text-3);
}

.el-dialog,
.el-drawer {
  border-radius: 18px 18px 0 0;
}

.el-tag {
  border-radius: 999px;
  padding-inline: 10px;
  font-weight: 600;
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

  .section-title h1 {
    font-size: 26px;
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

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
</style>
