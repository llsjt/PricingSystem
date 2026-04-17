import test from 'node:test'
import assert from 'node:assert/strict'

import { toUserFacingErrorMessage } from '../src/utils/error.ts'

test('toUserFacingErrorMessage converts English login failure into Chinese fallback', () => {
  assert.equal(
    toUserFacingErrorMessage('Invalid username or password', '登录失败，请检查用户名或密码'),
    '登录失败，请检查用户名或密码'
  )
})
