import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const apiSource = await readFile(join(root, 'src', 'api', 'decision.ts'), 'utf8')
const archiveSource = await readFile(join(root, 'src', 'views', 'Archive.vue'), 'utf8')
const archiveLogicSource = await readFile(join(root, 'src', 'composables', 'useArchivePage.ts'), 'utf8')

assert.match(apiSource, /deleteDecisionTask/, 'decision api exposes single archive deletion')
assert.match(apiSource, /batchDeleteDecisionTasks/, 'decision api exposes batch archive deletion')
assert.match(apiSource, /request\.delete\(`\/decision\/tasks\/\$\{taskId\}`\)/, 'single archive deletion uses the task endpoint')
assert.match(apiSource, /ids\.join\(','\)/, 'batch archive deletion sends ids as comma-separated query params')

assert.match(archiveSource, /type="selection"/, 'archive table allows selecting multiple decision records')
assert.match(
  archiveSource,
  /<el-table-column[^>]*type="selection"[^>]*:reserve-selection="true"/s,
  'archive table preserves selections when paging'
)
assert.match(archiveSource, /selectedTaskIds\.length/, 'archive page shows selected decision count')
assert.match(archiveSource, /handleDeleteTask\(row\)/, 'archive row actions include single delete')
assert.match(archiveSource, /handleBatchDeleteTasks/, 'archive toolbar includes batch delete')

assert.match(archiveLogicSource, /selectedTaskIds = ref<number\[\]>\(\[\]\)/, 'archive logic tracks selected task ids')
assert.match(archiveLogicSource, /currentPageIds/, 'archive selection logic identifies rows on the current page')
assert.match(archiveLogicSource, /selectedSet\.delete/, 'archive selection logic removes only deselected current-page ids')
assert.match(archiveLogicSource, /selectedSet\.add/, 'archive selection logic keeps selected ids from other pages')
assert.match(archiveLogicSource, /const handleDeleteTask = async/, 'archive logic implements single delete')
assert.match(archiveLogicSource, /const handleBatchDeleteTasks = async/, 'archive logic implements batch delete')
assert.match(archiveLogicSource, /batchDeleteDecisionTasks\(selectedTaskIds\.value\)/, 'archive logic calls batch delete api with selected ids')

console.log('archive delete tests passed')
