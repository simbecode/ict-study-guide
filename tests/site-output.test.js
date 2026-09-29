'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const titleOf = file => (read(file).match(/<title>(.*?)<\/title>/s) || [])[1];

assert.equal(titleOf('s2/osi/index.html'), 'OSI 7계층 전체 지도 | 정보통신기사 필기 2과목');
assert.equal(titleOf('overview/index.html'), 'OSI 7계층 한눈에 | 정보통신기사 필기');
assert.equal(titleOf('quiz/2022-1/index.html'), '2022년 1회 기출문제 해설 | 정보통신기사 필기');
assert.equal(titleOf('radix/index.html'), '진수 변환 한눈에 | 정보통신기사 필기');

assert.ok(fs.statSync(path.join(root, 'index.html')).size < 100000, '홈 HTML은 100KB 미만이어야 한다');
assert.equal((read('quiz/2022-1/index.html').match(/class="qy-item"/g) || []).length, 100);
assert.doesNotMatch(read('sections/quiz.html'), /8개 이하 과락|12개 이상 합격/);
assert.doesNotMatch(read('sitemap.xml'), /cbt-2026-4|osi_study_guide\.html|<loc>https:\/\/ict\.kyufind\.com\/subnet\/<\/loc>/);
assert.match(read('index.html'), /data-sec="radix-essential"[^>]*>진수 변환 한눈에<\/a>/);
assert.match(read('radix/index.html'), /href="\/s1\/radix\/"[^>]*>.*1과목 진수 변환 전체 내용에서 공부하기/s);
const radixPage = read('radix/index.html');
assert.ok(radixPage.indexOf('① 10진수에서 2·8·16진수로 변환') < radixPage.indexOf('② 2·8·16진수에서 10진수로 변환'));
assert.match(read('factory-utilization/index.html'), /가동률 = .*MTBF.*÷ \(.*MTBF.*\+.*MTTR.*\)/s);
assert.match(read('assets/app.css'), /\.fr\{display:inline-flex;flex-direction:column/);

const app = read('assets/app.js');
for(const eventName of ['cbt_answer', 'cbt_complete', 'quiz_submit', 'card_flip']){
  assert.match(app, new RegExp("trackEvent\\('" + eventName + "'"));
}

console.log('정적 페이지 출력 테스트 통과');
