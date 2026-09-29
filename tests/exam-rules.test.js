'use strict';

const assert = require('node:assert/strict');
const rules = require('../assets/exam-rules.js');

assert.equal(rules.isSubjectFailed(7, 20), true, '7/20(35점)은 과락이어야 한다');
assert.equal(rules.isSubjectFailed(8, 20), false, '8/20(40점)은 과락이 아니어야 한다');

const belowSixty = rules.evaluateScores([59.5, 60, 60, 60, 60]);
assert.equal(belowSixty.average, 59.9);
assert.equal(belowSixty.passed, false, '평균 59.x점은 불합격이어야 한다');

const exactlySixty = rules.evaluateScores([60, 60, 60, 60, 60]);
assert.equal(exactlySixty.average, 60);
assert.equal(exactlySixty.passed, true, '평균 60점이고 과락이 없으면 합격이어야 한다');

const failedSubject = rules.evaluateSubjects([
  {correct: 7, total: 20},
  {correct: 20, total: 20},
  {correct: 20, total: 20},
  {correct: 20, total: 20},
  {correct: 20, total: 20}
]);
assert.equal(failedSubject.average, 87);
assert.equal(failedSubject.passed, false, '평균이 높아도 한 과목이 40점 미만이면 불합격이어야 한다');

console.log('exam-rules 경계값 테스트 통과');
