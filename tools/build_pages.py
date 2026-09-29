#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주제별 페이지 생성기 — 검색엔진이 주제마다 따로 찾을 수 있도록 고유 주소 페이지를 만든다.

  실행:  python tools/build_pages.py        (저장소 폴더에서, 파이썬 3.7 이상, 추가 설치 없음)

  원본(직접 수정하는 파일)
    index.html            홈 화면이자 전체 화면 틀(CSS·JS 포함)
    subjects/*.html       과목별 본문
    data/quiz/*.json      기출문제

  자동 생성(직접 수정하지 말 것 — 원본을 고치고 이 스크립트를 다시 실행)
    s1/ ~ s5/             과목 모음(/s1/)과 주제 페이지(/s1/csma/ …)
    cram/ cbt-2026-4/ quiz/
    assets/app.css, assets/app.js, assets/routes.js
    sections/cbt26.html
    sitemap.xml
    index.html 의 사이드바 링크 주소(href)만 자동으로 맞춘다.

  index.html 이나 subjects/ 를 고쳤다면 커밋 전에 이 스크립트를 한 번 실행하세요.
"""
import datetime
import hashlib
import html
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://ict.kyufind.com'
GEN_LIST = os.path.join(ROOT, 'tools', 'generated-files.txt')

# ── 검색결과에 보이는 문구 ────────────────────────────────
# 제목: 구글 한국어 검색결과는 약 30자에서 잘린다. 주제명을 앞에 두고 접미사는 짧게 유지한다.
# 설명: 약 80자까지만 노출된다. 80자를 넘기면 뒤가 잘리므로 DESC_MAX 안에서 끝낸다.
TITLE_SUFFIX = ' | 정보통신기사 필기'
DESC_MAX = 88

# 과목 외 단독 페이지: 섹션 id → (주소, 검색 설명, 페이지 제목)
EXTRA_PAGES = {
    'factory-utilization': ('/factory-utilization/', 'MTTF·MTTR·MTBF의 뜻과 설비 가동률·불가동률 공식, 기출 계산 예제와 공장 설비 적용 방법을 한눈에 정리합니다.',
                            '공장가동률 한눈에 — MTTF·MTTR·MTBF' + TITLE_SUFFIX),
    'cram': ('/cram/', '기출에 나온 나이퀴스트·섀넌·데시벨·BER·다중화 계산 공식과 설비기준·법규 숫자, 두 번 이상 나온 문제를 한 페이지에 모았습니다.',
             '시험 직전 요약 — 계산 공식·법규 숫자' + TITLE_SUFFIX),
    'cbt26': ('/cbt-2026/', '응시 후기로 모은 2026년 출제 주제를 바탕으로 만든 복원 문제 69개. 개념 정리와 확인 문제, 변형 문제, 오답 복습까지 이어집니다.',
              '2026년 시험복원문제 69문항' + TITLE_SUFFIX),
    'quiz': ('/quiz/', '2022~2023년 기출 500문항을 회차별·과목별로 골라 풀고, 해설과 과목별 점수·틀린 문제를 확인하는 무료 CBT 연습.',
             '기출문제 500제 — 회차별 CBT 풀이' + TITLE_SUFFIX),
}

# 주소가 바뀐 페이지: 옛 주소 → 새 주소.
# GitHub Pages 는 서버 리다이렉트를 못 하므로, 옛 주소에 canonical + 즉시 이동 페이지를 남긴다.
REDIRECTS = {
    '/cbt-2026-4/': '/cbt-2026/',      # 2026-09-22 '2026년 시험복원문제' 로 이름 변경
}

# 회차별 기출 페이지 — data/quiz/*.json 하나당 한 페이지(/quiz/2022-1/)
QUIZ_CSS = ('<style>'
            '.qy-lead{font-size:14.5px;color:var(--text2);line-height:1.75;margin:-4px 0 22px}'
            '.qy-meta{display:flex;gap:8px;flex-wrap:wrap;font-size:12.5px;color:var(--text3);margin:0 0 18px}'
            '.qy-meta span{border:1px solid var(--border);border-radius:20px;padding:3px 11px;background:var(--bg2)}'
            '.qy-subj{margin:34px 0 14px;font-size:17px;font-weight:800;color:var(--text);'
            'padding-bottom:7px;border-bottom:2px solid var(--border)}'
            '.qy-list{list-style:none;margin:0;padding:0;display:grid;gap:14px}'
            '.qy-item{border:1px solid var(--border);border-radius:10px;background:var(--bg2);padding:15px 18px}'
            '.qy-q{font-size:15px;font-weight:600;line-height:1.7;margin:0 0 11px}'
            '.qy-q .qy-no{color:var(--key);font-family:var(--mono);font-weight:700;margin-right:7px}'
            '.qy-opts{list-style:none;margin:0;padding:0;display:grid;gap:5px}'
            '.qy-opts li{font-size:14px;line-height:1.65;color:var(--text2);padding:5px 10px;border-radius:6px}'
            '.qy-opts li.ok{background:var(--ok-bg);color:var(--ok);font-weight:700}'
            '.qy-ex{margin:11px 0 0;padding:10px 13px;border-left:3px solid var(--key-bd);'
            'background:var(--key-bg);border-radius:0 7px 7px 0;font-size:13.5px;line-height:1.7;color:var(--text2)}'
            '.qy-ex b{color:var(--key)}'
            '.qy-foot{margin:34px 0 0;padding-top:18px;border-top:1px solid var(--border);'
            'font-size:13px;color:var(--text3);display:flex;gap:8px;flex-wrap:wrap;align-items:center}'
            '.qy-foot a{display:inline-block;padding:5px 11px;border:1px solid var(--border);border-radius:7px;'
            'background:var(--bg2);color:var(--text2);text-decoration:none;font-weight:600}'
            '.qy-foot a:hover{border-color:var(--key-bd);background:var(--key-bg);color:var(--key)}'
            '</style>')
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'

# 과목 모음 페이지(/s1/ 등)의 검색 설명 — 주제 이름을 그대로 나열하면 80자를 금방 넘겨 잘린다.
HUB_DESC = {
    's1': '정보전송일반 핵심 주제 23개 — 변조, 다중화, PCM, 광통신, 오류 제어와 나이퀴스트·BER 계산 공식을 주제별로 정리.',
    's2': '정보통신기기 핵심 주제 — UTP 케이블, OSI 전체 지도, 광가입자망, 이동통신 1G~5G, CCTV·CATV, 교환기를 주제별로 정리.',
    's3': '정보통신네트워크 핵심 주제 15개 — OSI 7계층 상세, TCP/UDP, 서브넷팅, 라우팅 프로토콜, 포트번호, 토폴로지를 정리.',
    's4': '정보시스템운용 핵심 주제 — 암호화, 클라우드, MTBF 가동률, SNMP 망관리, 백업·RAID, 보안 위협과 보안 장비를 정리.',
    's5': '컴퓨터일반 및 정보설비기준 핵심 주제 — CPU와 운영체제, 자료구조, 데이터베이스, 전기통신사업법·공사업법·기술기준.',
}

EMOJI_RX = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\uFE0F\u200D\u3030]')


def rd(path):
    with open(os.path.join(ROOT, path), encoding='utf-8', newline='') as f:
        return f.read()


def wr(path, text, generated):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    old = None
    if os.path.exists(full):
        with open(full, encoding='utf-8', newline='') as f:
            old = f.read()
    if old != text:
        with open(full, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    if generated is not None:
        generated.append(path.replace('\\', '/'))
    return old != text


def balanced_div(s, start):
    """s[start] 에서 시작하는 <div ...> 의 닫는 </div> 까지 잘라낸다."""
    tag = re.compile(r'<(/?)div\b', re.I)
    depth = 0
    for m in tag.finditer(s, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            end = s.index('>', m.end()) + 1
            return s[start:end]
    raise ValueError('닫히지 않은 div: %d' % start)


def text_of(fragment):
    t = re.sub(r'<(script|style)\b.*?</\1>', ' ', fragment, flags=re.S | re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html.unescape(t)
    t = EMOJI_RX.sub('', t)
    return re.sub(r'\s+', ' ', t).strip()


def clean_title(t):
    t = EMOJI_RX.sub('', text_of(t))
    t = re.sub(r'\s*\((?:[\d·]+과목)\)\s*$', '', t)
    return t.strip()


def clip(t, n):
    if len(t) <= n:
        return t
    cut = t[:n]
    sp = cut.rfind(' ')
    return (cut[:sp] if sp > n * 0.6 else cut).rstrip(' ,·.—-') + '…'


def clip_sentence(t, n=DESC_MAX):
    """문장 경계에서 끊어 검색결과에 잘리지 않는 설명문을 만든다.

    data-desc 가 없는 섹션의 폴백이다. 예전에는 본문 앞부분을 글자 수로만 잘라
    "…처리하느냐 에 따라 CD와…" 처럼 조사 앞에서 끊기는 문장이 나왔다.
    """
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= n:
        return t
    parts = re.split(r'(?<=[.!?。])\s+|(?<=다)\.\s*', t)
    out = ''
    for p in parts:
        p = p.strip()
        if not p:
            continue
        cand = (out + ' ' + p).strip() if out else p
        if len(cand) > n:
            break
        out = cand
    if not out:                       # 첫 문장부터 길면 글자 수로 자른다
        return clip(t, n)
    return out if out.endswith(('.', '!', '?')) else out + '.'


def git_date(*paths):
    best = ''
    for p in paths:
        try:
            out = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', p], cwd=ROOT,
                                 capture_output=True, text=True, timeout=20).stdout.strip()
            best = max(best, out)
        except Exception:
            pass
    return best or datetime.date.today().isoformat()


def esc(t):
    return html.escape(t, quote=True)


def main():
    index = rd('index.html')
    NL = '\r\n' if '\r\n' in index else '\n'

    # ── 과목 이름 (사이드바 기준) ─────────────────────────────
    subj_names = {}
    for m in re.finditer(r'data-sid="(s\d)"[^>]*>.*?<span class="subj-name">([^<]+)</span>', index):
        subj_names[m.group(1)] = re.sub(r'^\d\.\s*', '', m.group(2)).strip()

    # 사이드바 과목별 항목 순서
    side_items = {}
    for m in re.finditer(r'<div class="subj-items" id="(s\d)">', index):
        block = balanced_div(index, m.start())
        items = []
        for it in re.finditer(r'<div class="nav-group">([^<]+)</div>|<a class="sub-item" href="[^"]*" data-sec="([^"]+)"[^>]*>(.*?)</a>', block):
            if it.group(1):
                items.append(('group', it.group(1).strip(), None))
            else:
                items.append(('item', it.group(2), text_of(it.group(3))))
        side_items[m.group(1)] = items
    side_label = {}
    for items in side_items.values():
        for kind, a, b in items:
            if kind == 'item':
                side_label.setdefault(a, b)

    # ── 과목 본문의 섹션 ─────────────────────────────────────
    sections = {}   # id -> dict
    subj_files = sorted(f for f in os.listdir(os.path.join(ROOT, 'subjects')) if f.endswith('.html'))
    for fn in subj_files:
        sid = 's' + fn.split('-')[0]
        src = rd('subjects/' + fn)
        for m in re.finditer(r'<div class="section[^"]*" id="sec-([^"]+)"', src):
            sec = m.group(1)
            if sec in sections:
                continue
            block = balanced_div(src, m.start())
            h = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.S)
            title = clean_title(h.group(1)) if h else side_label.get(sec, sec)
            body = text_of(block[h.end():] if h else block)
            # subjects/*.html 의 data-desc 가 검색결과 설명문이다(없으면 본문에서 자동 생성)
            open_tag = re.match(r'<div[^>]*>', block).group(0)
            dm = re.search(r'\sdata-desc="([^"]*)"', open_tag)
            desc = html.unescape(dm.group(1)).strip() if dm else ''
            # data-title 은 검색결과용 짧은 제목(화면의 h1 은 그대로 둔다)
            tm = re.search(r'\sdata-title="([^"]*)"', open_tag)
            seo_title = html.unescape(tm.group(1)).strip() if tm else ''
            sections[sec] = dict(id=sec, sid=sid, file='subjects/' + fn, html=block,
                                 title=title, body=body, desc=desc, seo_title=seo_title)

    missing = [k for k in side_label if k not in sections and k not in EXTRA_PAGES and k != 'home']
    if missing:
        print('주의: 사이드바에는 있지만 본문에 없는 섹션:', ', '.join(missing))

    # ── 경로 표 ──────────────────────────────────────────────
    home_title = text_of(re.search(r'<title>(.*?)</title>', index, re.S).group(1))
    routes = {'home': ['/', home_title]}
    for sid in sorted(subj_names):
        n = sid[1:]
        routes['hub-' + sid] = ['/%s/' % sid, '%s과목 %s 핵심정리%s' % (n, subj_names[sid], TITLE_SUFFIX)]
    for sec, d in sections.items():
        n = d['sid'][1:]
        d['url'] = '/%s/%s/' % (d['sid'], sec)
        d['page_title'] = (d['seo_title'] or d['title']) + TITLE_SUFFIX
        routes[sec] = [d['url'], d['page_title']]
    extra = {}
    for sec, (url, desc, ptitle) in EXTRA_PAGES.items():
        m = re.search(r'<div class="section[^"]*" id="sec-%s"' % re.escape(sec), index)
        if not m:
            print('주의: index.html 에 sec-%s 가 없어 건너뜀' % sec)
            continue
        block = balanced_div(index, m.start())
        h = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.S)
        title = clean_title(h.group(1)) if h else sec
        extra[sec] = dict(id=sec, url=url, desc=desc, html=block, title=title,
                          page_title=ptitle)
        routes[sec] = [url, extra[sec]['page_title']]

    # ── index.html 사이드바 링크 주소 맞추기 ─────────────────
    def fix_href(m):
        sec = m.group(2)
        url = routes.get(sec, ['/'])[0]
        return '%shref="%s" data-sec="%s"' % (m.group(1), url, sec)
    # 회차별 기출 페이지로 가는 링크 (검색엔진이 따라갈 수 있게 실제 <a> 로 넣는다)
    quiz_slugs = sorted(f[:-5] for f in os.listdir(os.path.join(ROOT, 'data', 'quiz'))
                        if f.endswith('.json')) if os.path.isdir(os.path.join(ROOT, 'data', 'quiz')) else []
    archive_html = ('<div id="quiz-archive" class="quiz-archive"><b>회차별 문제·해설 모아보기</b>'
                    + ''.join('<a href="/quiz/%s/">%s년 %s회</a>' % (sl, sl.split('-')[0], sl.split('-')[1])
                              for sl in quiz_slugs) + '</div>')

    def fill_archive(text):
        return re.sub(r'<div id="quiz-archive"[^>]*>.*?</div>', lambda m: archive_html, text, count=1, flags=re.S)

    new_index = re.sub(r'(<a class="sub-item[^"]*" )href="[^"]*" data-sec="([^"]+)"', fix_href, index)
    new_index = fill_archive(new_index)
    if wr('index.html', new_index, None):
        print('index.html 사이드바 링크 주소를 갱신했습니다.')
    index = new_index

    gen = []

    # ── 공용 파일 ────────────────────────────────────────────
    css_m = re.search(r'<style>(.*?)</style>', index, re.S)
    js_m = re.search(r'<script>(\s*let quizzes = \[\];.*?)</script>', index, re.S)
    assert css_m and js_m, 'index.html 에서 CSS/JS 블록을 찾지 못했습니다.'
    wr('assets/app.css', '/* 자동 생성: tools/build_pages.py — index.html 의 첫 <style> 복사본. 직접 수정하지 마세요. */\n' + css_m.group(1).strip() + '\n', gen)
    wr('assets/app.js', '// 자동 생성: tools/build_pages.py — index.html 의 본문 스크립트 복사본. 직접 수정하지 마세요.\n' + js_m.group(1).strip() + '\n', gen)
    wr('assets/routes.js', '// 자동 생성: tools/build_pages.py — 주제별 주소 목록\nwindow.__ROUTES__ = ' + json.dumps(routes, ensure_ascii=False, indent=0) + ';\n', gen)

    # ── 페이지 틀 ────────────────────────────────────────────
    tpl = index
    tpl = tpl.replace(css_m.group(0), '<link rel="stylesheet" href="/assets/app.css">', 1)
    js_version = hashlib.sha256(js_m.group(1).encode('utf-8')).hexdigest()[:12]
    tpl = tpl.replace(js_m.group(0), '<script src="/assets/app.js?v=' + js_version + '"></script>', 1)
    tpl = tpl.replace('<div class="section visible" id="sec-home">', '<div class="section" id="sec-home">', 1)
    tpl = tpl.replace('<h1 class="home-title">', '<p class="home-title">', 1)
    tpl = re.sub(r'(<p class="home-title">[^<]*)</h1>', r'\1</p>', tpl, count=1)
    tpl = fill_archive(tpl)

    # ── 공용 섹션 분리 ───────────────────────────────────────
    # 홈·시험직전요약·CBT·용어카드·기출 은 어느 페이지에서나 똑같은 내용이다.
    # 이걸 71개 페이지 HTML 에 그대로 넣으면 주제 페이지 본문의 절반 이상이 중복돼
    # 검색엔진이 "이 페이지가 무엇에 대한 페이지인지" 판단할 근거가 흐려진다.
    # 그래서 sections/*.html 로 빼고, 해당 내용이 주인공인 페이지에서만 본문에 넣는다.
    # 나머지 페이지는 슬롯만 두고 app.js 가 화면 표시 뒤에 불러온다.
    SLOT_SECTIONS = ['factory-utilization', 'home', 'cram', 'cbt26', 'cards', 'quiz']
    slot_div = {}
    for name in SLOT_SECTIONS:
        m = re.search(r'<div class="section[^"]*" id="sec-%s"' % re.escape(name), tpl)
        if not m:
            print('주의: 공용 섹션 sec-%s 를 찾지 못해 건너뜁니다' % name)
            continue
        block = balanced_div(tpl, m.start())
        wr('sections/%s.html' % name, block + '\n', gen)
        slot_div[name] = '<div data-section-src="/sections/%s.html"></div>' % name
        tpl = tpl.replace(block, slot_div[name], 1)

    root_m = re.search(r'<div id="subject-content-root">.*?</div></div>', tpl)
    assert root_m, 'subject-content-root 를 찾지 못했습니다.'

    # ── 빵부스러기(경로 표시) ────────────────────────────────
    # 기존 #crumb 는 JS 가 채우는 빈 div 라서 검색엔진이 따라갈 링크가 없었다.
    # 과목 모음 페이지(/s1/ 등)로 가는 실제 <a> 를 HTML 에 미리 넣는다.
    CRUMB_EMPTY = '<div id="crumb" class="crumb" hidden></div>'
    assert CRUMB_EMPTY in tpl, '#crumb 를 찾지 못했습니다.'

    def crumb_links(sid, label, url, tag='div', attrs=' id="crumb"'):
        return ('<%s%s class="crumb c-%s" aria-label="경로">'
                '<a class="crumb-link" href="/">홈</a><span class="crumb-sep">/</span>'
                '<span class="crumb-dot" style="background:var(--sc)"></span>'
                '<a class="crumb-link" href="%s" style="color:var(--sct)"><b>%s</b></a>'
                '</%s>') % (tag, attrs, sid, url, esc(label), tag)

    def set_meta(t, title, desc, url, crumbs, lr_name):
        t = re.sub(r'<title>.*?</title>', lambda m: '<title>%s</title>' % esc(title), t, count=1, flags=re.S)
        t = re.sub(r'<meta name="description" content="[^"]*">', lambda m: '<meta name="description" content="%s">' % esc(desc), t, count=1)
        t = re.sub(r'<link rel="canonical" href="[^"]*">', lambda m: '<link rel="canonical" href="%s">' % (SITE + url), t, count=1)
        t = re.sub(r'<meta property="og:title" content="[^"]*">', lambda m: '<meta property="og:title" content="%s">' % esc(title), t, count=1)
        t = re.sub(r'<meta property="og:description" content="[^"]*">', lambda m: '<meta property="og:description" content="%s">' % esc(desc), t, count=1)
        t = re.sub(r'<meta property="og:url" content="[^"]*">', lambda m: '<meta property="og:url" content="%s">' % (SITE + url), t, count=1)
        t = t.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="article">', 1)
        t = re.sub(r'<meta name="twitter:title" content="[^"]*">', lambda m: '<meta name="twitter:title" content="%s">' % esc(title), t, count=1)
        t = re.sub(r'<meta name="twitter:description" content="[^"]*">', lambda m: '<meta name="twitter:description" content="%s">' % esc(desc), t, count=1)
        ld = [{
            '@context': 'https://schema.org', '@type': 'BreadcrumbList',
            'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': nm, 'item': SITE + u}
                                for i, (nm, u) in enumerate(crumbs)]
        }, {
            '@context': 'https://schema.org', '@type': 'LearningResource',
            'name': lr_name, 'description': desc, 'url': SITE + url, 'inLanguage': 'ko',
            'isAccessibleForFree': True, 'learningResourceType': 'study guide',
            'educationalLevel': 'professional certification',
            'about': {'@type': 'Thing', 'name': '정보통신기사'},
            'isPartOf': {'@type': 'WebSite', 'name': '정보통신기사 필기 학습 가이드', 'url': SITE + '/'}
        }]
        ld_txt = json.dumps(ld, ensure_ascii=False, indent=1).replace('</', '<\\/')
        t = re.sub(r'<script type="application/ld\+json">.*?</script>',
                   lambda m: '<script type="application/ld+json">\n' + ld_txt + '\n</script>', t, count=1, flags=re.S)
        return t

    def mark_active(t, sec):
        return re.sub(r'<a class="(sub-item[^"]*)" (href="[^"]*" data-sec="%s")' % re.escape(sec),
                      lambda m: '<a class="%s active" aria-current="page" %s' % (m.group(1), m.group(2)), t, count=1)

    def page_script(info):
        return '<script src="/assets/routes.js"></script>' + NL + '<script>window.__PAGE__ = ' + json.dumps(info, ensure_ascii=False) + ';</script>'

    def as_visible(block, h1=True):
        b = re.sub(r'^<div class="section[^"]*"', lambda m: m.group(0).replace('class="section', 'class="section visible', 1), block, count=1)
        if h1:
            b = re.sub(r'<h2 class="section-title"(.*?)</h2>', r'<h1 class="section-title"\1</h1>', b, count=1, flags=re.S)
        return b

    written = 0
    home_crumb = ('홈', '/')

    # 주제 페이지
    for sec, d in sections.items():
        n = d['sid'][1:]
        sname = subj_names.get(d['sid'], '')
        desc = d['desc'] or clip_sentence('정보통신기사 필기 %s과목 %s — %s. %s' % (n, sname, d['title'], d['body']))
        t = set_meta(tpl, d['page_title'], desc, d['url'],
                     [home_crumb, ('%s과목 %s' % (n, sname), '/%s/' % d['sid']), (d['title'], d['url'])],
                     d['title'])
        t = t.replace('<script src="/assets/routes.js"></script>', page_script({'sec': sec}), 1)
        t = t.replace(root_m.group(0), '<div id="subject-content-root">' + as_visible(d['html']) + '</div>', 1)
        t = t.replace(CRUMB_EMPTY, crumb_links(d['sid'], '%s과목 %s' % (n, sname), '/%s/' % d['sid']), 1)
        t = mark_active(t, sec)
        written += wr('%s/%s/index.html' % (d['sid'], sec), t, gen)

    # 과목 모음 페이지
    hub_css = ('<style>.hub-lead{font-size:15px;color:var(--text2);margin:-6px 0 22px;line-height:1.7}'
               '.hub-group{margin:26px 0 8px;font-size:13px;font-weight:700;color:var(--text3)}'
               '.hub-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}'
               '.hub-list a{display:block;padding:12px 16px;border:1px solid var(--border);border-radius:10px;background:var(--bg2);text-decoration:none;color:var(--text)}'
               '.hub-list a:hover{border-color:var(--key-bd);background:var(--key-bg)}'
               '.hub-list b{display:block;font-size:15px;margin-bottom:3px}'
               '.hub-list span{display:block;font-size:13px;color:var(--text3);line-height:1.55}</style>')
    for sid in sorted(subj_names):
        n = sid[1:]
        sname = subj_names[sid]
        url = '/%s/' % sid
        lis, count = [], 0
        for kind, a, b in side_items.get(sid, []):
            if kind == 'group':
                lis.append('</ul><div class="hub-group">%s</div><ul class="hub-list">' % esc(a))
                continue
            d = sections.get(a)
            if not d:
                continue
            count += 1
            lis.append('<li><a href="%s" onclick="return navGo(event,\'%s\',this)"><b>%s</b><span>%s</span></a></li>'
                       % (d['url'], a, esc(b or d['title']), esc(clip(d['body'], 90))))
        # #crumb 는 JS(syncNav)가 과목 모음 페이지에서 비워버리므로, 본문 안에 따로 넣는다
        hub_crumb = ('<nav class="crumb c-%s" aria-label="경로">'
                     '<a class="crumb-link" href="/">홈</a><span class="crumb-sep">/</span>'
                     '<span class="crumb-dot" style="background:var(--sc)"></span>'
                     '<b style="color:var(--sct)">%s과목 %s</b></nav>') % (sid, n, esc(sname))
        body = ('<div class="section visible" id="sec-hub-%s">%s%s<h1 class="section-title">%s과목 %s</h1>'
                '<p class="hub-lead">정보통신기사 필기 %s과목 <b>%s</b>의 핵심 주제 %d개입니다. 주제를 누르면 정리 페이지로 이동합니다.</p>'
                '<ul class="hub-list">%s</ul></div>') % (sid, hub_css, hub_crumb, n, esc(sname), n, esc(sname), count, ''.join(lis))
        body = body.replace('<ul class="hub-list"></ul>', '')
        desc = HUB_DESC.get(sid)
        if not desc:
            titles = ', '.join(sections[a]['title'] for k, a, _ in side_items.get(sid, []) if k == 'item' and a in sections)
            desc = clip_sentence('정보통신기사 필기 %s과목 %s 핵심정리 주제 모음 — %s' % (n, sname, titles))
        t = set_meta(tpl, routes['hub-' + sid][1], desc, url,
                     [home_crumb, ('%s과목 %s' % (n, sname), url)], '%s과목 %s 핵심정리' % (n, sname))
        t = t.replace('<script src="/assets/routes.js"></script>', page_script({'hub': sid}), 1)
        t = t.replace(root_m.group(0), body + root_m.group(0), 1)
        written += wr('%s/index.html' % sid, t, gen)

    # 단독 페이지 (요약 · CBT · 기출)
    for sec, d in extra.items():
        t = set_meta(tpl, d['page_title'], d['desc'], d['url'], [home_crumb, (d['title'], d['url'])], d['title'])
        t = t.replace('<script src="/assets/routes.js"></script>', page_script({'sec': sec}), 1)
        # 이 페이지가 주인공인 섹션만 본문에 넣는다 (나머지는 슬롯 그대로 두고 app.js 가 불러옴)
        assert sec in slot_div, 'sec-%s 슬롯을 찾지 못했습니다.' % sec
        # 회차 링크는 index.html 을 다시 쓰기 전에 떠 온 블록이라 여기서 한 번 더 채운다
        t = t.replace(slot_div[sec], as_visible(fill_archive(d['html'])), 1)
        t = mark_active(t, sec)
        written += wr(d['url'].strip('/') + '/index.html', t, gen)

    # ── 회차별 기출 페이지 ───────────────────────────────────
    # /quiz/ 는 문제를 JSON 에서 JS 로 불러와 화면에 몇 개씩만 그리므로 HTML 에 본문이 거의 없다.
    # 회차마다 100문항과 해설을 그대로 담은 정적 페이지를 따로 만들어 검색엔진이 읽게 한다.
    quiz_pages = []
    quiz_dir = os.path.join(ROOT, 'data', 'quiz')
    for qf in sorted(os.listdir(quiz_dir)) if os.path.isdir(quiz_dir) else []:
        if not qf.endswith('.json'):
            continue
        slug = qf[:-5]                                   # 2022-1
        with open(os.path.join(quiz_dir, qf), encoding='utf-8') as f:
            items = json.load(f)
        if not items:
            continue
        yr, rnd = slug.split('-')[0], slug.split('-')[1]
        label = '%s년 %s회' % (yr, rnd)
        quiz_pages.append(dict(slug=slug, label=label, url='/quiz/%s/' % slug,
                               items=items, file='data/quiz/' + qf))

    def quiz_body(pg_, others):
        by_subj = {}
        for it in pg_['items']:
            by_subj.setdefault(it.get('subj') or '기타', []).append(it)
        parts = []
        for subj in sorted(by_subj):
            sid_ = 's' + subj[0] if subj and subj[0].isdigit() else ''
            sname_ = subj_names.get(sid_, '')
            head = '%s %s' % (subj, sname_) if sname_ else subj
            link = ('<a href="/%s/">%s</a>' % (sid_, esc(head))) if sid_ in subj_names else esc(head)
            # sub-title 을 함께 주면 오른쪽 "이 페이지에서" 목차(buildToc)에 잡힌다
            parts.append('<h2 class="qy-subj sub-title">%s</h2><ol class="qy-list">' % link)
            for it in by_subj[subj]:
                ans = it.get('ans')
                opts = []
                for i, o in enumerate(it.get('opts') or []):
                    ok = ' class="ok"' if i == ans else ''
                    opts.append('<li%s>%s %s</li>' % (ok, CIRCLED[i:i + 1] or '-', esc(str(o))))
                ex = it.get('ex') or ''
                mark = CIRCLED[ans:ans + 1] if isinstance(ans, int) and 0 <= ans < len(CIRCLED) else '-'
                parts.append('<li class="qy-item" id="q%s">'
                             '<p class="qy-q"><span class="qy-no">%s번</span>%s</p>'
                             '<ol class="qy-opts">%s</ol>'
                             '<p class="qy-ex"><b>정답 %s</b>%s</p></li>'
                             % (esc(str(it.get('n', ''))), esc(str(it.get('n', ''))), esc(str(it.get('q', ''))),
                                ''.join(opts), mark, (' — ' + esc(ex)) if ex else ''))
            parts.append('</ol>')
        foot = ('<nav class="qy-foot"><span>다른 회차</span>'
                + ''.join('<a href="%s">%s</a>' % (o['url'], esc(o['label'])) for o in others)
                + '<a href="/quiz/">풀이 모드로 풀기</a></nav>')
        crumb = ('<nav class="crumb" aria-label="경로">'
                 '<a class="crumb-link" href="/">홈</a><span class="crumb-sep">/</span>'
                 '<a class="crumb-link" href="/quiz/">기출문제</a><span class="crumb-sep">/</span>'
                 '<b>%s</b></nav>') % esc(pg_['label'])
        return ('<div class="section visible" id="sec-quizyear-%s">%s%s'
                '<h1 class="section-title">정보통신기사 필기 %s 기출문제</h1>'
                '<p class="qy-lead">%s 필기 기출 %d문항 전체와 해설입니다. 과목별로 묶었고, '
                '정답 보기는 초록색으로 표시했습니다. 직접 풀어 보려면 '
                '<a href="/quiz/">기출문제 풀이 모드</a>를 이용하세요.</p>'
                '<div class="qy-meta"><span>%d문항</span><span>5과목</span><span>해설 포함</span></div>'
                '%s%s</div>') % (pg_['slug'], QUIZ_CSS, crumb, esc(pg_['label']), esc(pg_['label']),
                                 len(pg_['items']), len(pg_['items']), ''.join(parts), foot)

    for pg_ in quiz_pages:
        others = [o for o in quiz_pages if o['slug'] != pg_['slug']]
        ptitle = '%s 기출문제 해설%s' % (pg_['label'], TITLE_SUFFIX)
        pdesc = ('정보통신기사 필기 %s 기출문제 %d문항 전체와 해설. 과목별로 묶어 정답과 풀이를 함께 실었습니다.'
                 % (pg_['label'], len(pg_['items'])))
        routes['quizyear-' + pg_['slug']] = [pg_['url'], ptitle]
        t = set_meta(tpl, ptitle, pdesc, pg_['url'],
                     [home_crumb, ('기출문제', '/quiz/'), (pg_['label'], pg_['url'])],
                     '%s 기출문제' % pg_['label'])
        t = t.replace('<script src="/assets/routes.js"></script>',
                      page_script({'sec': 'quizyear-' + pg_['slug'], 'nav': 'quiz'}), 1)
        t = t.replace(root_m.group(0), quiz_body(pg_, others) + root_m.group(0), 1)
        written += wr('quiz/%s/index.html' % pg_['slug'], t, gen)

    # routes.js 는 회차 주소까지 담아야 뒤로가기·주소 동기화가 맞는다 → 여기서 다시 쓴다
    wr('assets/routes.js', '// 자동 생성: tools/build_pages.py — 주제별 주소 목록\nwindow.__ROUTES__ = '
       + json.dumps(routes, ensure_ascii=False, indent=0) + ';\n', None)

    # ── 옛 주소 안내 페이지 ──────────────────────────────────
    for old_url, new_url in REDIRECTS.items():
        page = ('<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="UTF-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                '<link rel="canonical" href="%s%s">\n'
                '<meta http-equiv="refresh" content="0; url=%s">\n'
                '<title>주소가 바뀌었습니다 — 정보통신기사 필기</title>\n'
                '<style>body{font-family:system-ui,-apple-system,"Malgun Gothic",sans-serif;'
                'background:#fafcfe;color:#1d252d;display:flex;align-items:center;justify-content:center;'
                'min-height:100vh;margin:0;padding:24px;text-align:center;line-height:1.7}'
                'a{color:#2769b7}</style>\n</head>\n<body>\n'
                '<p>이 페이지의 주소가 <b>%s</b> 로 바뀌었습니다.<br>'
                '자동으로 이동하지 않으면 <a href="%s">여기를 눌러 주세요</a>.</p>\n'
                '</body>\n</html>\n') % (SITE, new_url, new_url, new_url, new_url)
        written += wr(old_url.strip('/') + '/index.html', page, gen)

    # ── sitemap.xml ──────────────────────────────────────────
    urls = [('/', git_date('index.html', 'subjects', 'data'), '1.0')]
    for sid in sorted(subj_names):
        f = [d['file'] for d in sections.values() if d['sid'] == sid]
        urls.append(('/%s/' % sid, git_date(*(f or ['index.html'])), '0.8'))
    for sec, d in extra.items():
        urls.append((d['url'], git_date('index.html', 'data') if sec == 'quiz' else git_date('index.html'), '0.8'))
    for pg_ in quiz_pages:
        urls.append((pg_['url'], git_date(pg_['file']), '0.7'))
    for d in sections.values():
        urls.append((d['url'], git_date(d['file']), '0.6'))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm, pr in urls:
        sm.append('  <url><loc>%s%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>' % (SITE, u, lm, pr))
    sm.append('</urlset>')
    wr('sitemap.xml', '\n'.join(sm) + '\n', None)

    # ── 더 이상 만들지 않는 옛 페이지 정리 ─────────────────────
    old = []
    if os.path.exists(GEN_LIST):
        with open(GEN_LIST, encoding='utf-8') as f:
            old = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    removed = 0
    for p in set(old) - set(gen):
        full = os.path.join(ROOT, p)
        if os.path.isfile(full):
            os.remove(full)
            removed += 1
            try:
                os.removedirs(os.path.dirname(full))
            except OSError:
                pass
    with open(GEN_LIST, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# tools/build_pages.py 가 만든 파일 목록 (다음 실행 때 없어진 페이지를 지우는 데 사용)\n')
        f.write('\n'.join(sorted(gen)) + '\n')

    print('완료: 페이지 %d개 (주제 %d · 과목 모음 %d · 단독 %d), 변경 %d개, 삭제 %d개, 사이트맵 주소 %d개'
          % (len(sections) + len(subj_names) + len(extra), len(sections), len(subj_names), len(extra),
             written, removed, len(urls)))


if __name__ == '__main__':
    main()
