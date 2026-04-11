const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

const repoRoot = process.cwd();
const databaseDir = path.join(repoRoot, 'database');

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8');
}

function hasChinese(text) {
  return /[\u4e00-\u9fff]/.test(text);
}

test('migrations with Chinese text pin the client charset', () => {
  const migrationFiles = fs
    .readdirSync(databaseDir)
    .filter((name) => /^migration_.*\.sql$/.test(name))
    .map((name) => path.join(databaseDir, name));

  const offenders = migrationFiles
    .map((filePath) => ({ filePath, content: read(filePath) }))
    .filter(({ content }) => hasChinese(content))
    .filter(({ content }) => !content.includes('SET NAMES utf8mb4;'));

  assert.deepEqual(
    offenders.map(({ filePath }) => path.basename(filePath)),
    [],
    `Missing SET NAMES utf8mb4: ${offenders.map(({ filePath }) => path.basename(filePath)).join(', ')}`,
  );
});

test('mysql helper and import scripts force utf8mb4', () => {
  const files = [
    path.join(repoRoot, 'scripts', 'public-beta-common.ps1'),
    path.join(repoRoot, 'scripts', 'apply-db-migrations.ps1'),
    path.join(repoRoot, 'scripts', 'db-restore.ps1'),
    path.join(repoRoot, 'scripts', 'db-backup.ps1'),
  ];

  const missing = files.filter((filePath) => !read(filePath).includes('--default-character-set=utf8mb4'));

  assert.deepEqual(
    missing.map((filePath) => path.basename(filePath)),
    [],
    `Missing --default-character-set=utf8mb4: ${missing.map((filePath) => path.basename(filePath)).join(', ')}`,
  );
});
