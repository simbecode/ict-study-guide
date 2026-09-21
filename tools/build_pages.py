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

# 과목 외 단독 페이지: 섹션 id → (주소, 검색 설명, 페이지 제목)
EXTRA_PAGES = {
    'cram': ('/cram/', '정보통신기사 필기 시험 직전 요약 — 기출에 나온 나이퀴스트·섀넌·데시벨·BER·다중화 계산 공식과 설비기준·법규 숫자, 두 번 이상 나온 문제를 한 페이지에 모았습니다.',
             '정보통신기사 필기 시험 직전 요약 — 계산 공식·법규 숫자·반복 기출'),
    'cbt26': ('/cbt-2026-4/', '정보통신기사 필기 2026년 4회 CBT 복원 예상문제 — 응시 후기로 모은 출제 주제를 바탕으로 만든 개념 정리와 확인 문제, 변형 문제, 오답 복습.',
              '2026년 4회 정보통신기사 필기 CBT 복원 예상문제 | 정보통신기사 필기'),
    'quiz': ('/quiz/', '정보통신기사 필기 기출문제 500제 — 2022~2023년 회차별·과목별로 골라 풀고 해설과 과목별 점수, 틀린 문제를 확인하는 무료 CBT 연습.',
             '정보통신기사 필기 기출문제 500제 — 회차별·과목별 CBT 풀이'),
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
            sections[sec] = dict(id=sec, sid=sid, file='subjects/' + fn, html=block, title=title, body=body)

    missing = [k for k in side_label if k not in sections and k not in EXTRA_PAGES and k != 'home']
    if missing:
        print('주의: 사이드바에는 있지만 본문에 없는 섹션:', ', '.join(missing))

    # ── 경로 표 ──────────────────────────────────────────────
    home_title = text_of(re.search(r'<title>(.*?)</title>', index, re.S).group(1))
    routes = {'home': ['/', home_title]}
    for sid in sorted(subj_names):
        n = sid[1:]
        routes['hub-' + sid] = ['/%s/' % sid, '%s과목 %s 핵심정리 — 주제 모음 | 정보통신기사 필기' % (n, subj_names[sid])]
    for sec, d in sections.items():
        n = d['sid'][1:]
        d['url'] = '/%s/%s/' % (d['sid'], sec)
        d['page_title'] = '%s | 정보통신기사 필기 %s과목 %s' % (d['title'], n, subj_names.get(d['sid'], ''))
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
    new_index = re.sub(r'(<a class="sub-item[^"]*" )href="[^"]*" data-sec="([^"]+)"', fix_href, index)
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

    cbt_block = extra['cbt26']['html'] if 'cbt26' in extra else None
    if cbt_block:
        wr('sections/cbt26.html', cbt_block + '\n', gen)

    # ── 페이지 틀 ────────────────────────────────────────────
    tpl = index
    tpl = tpl.replace(css_m.group(0), '<link rel="stylesheet" href="/assets/app.css">', 1)
    js_version = hashlib.sha256(js_m.group(1).encode('utf-8')).hexdigest()[:12]
    tpl = tpl.replace(js_m.group(0), '<script src="/assets/app.js?v=' + js_version + '"></script>', 1)
    tpl = tpl.replace('<div class="section visible" id="sec-home">', '<div class="section" id="sec-home">', 1)
    tpl = tpl.replace('<h1 class="home-title">', '<p class="home-title">', 1)
    tpl = re.sub(r'(<p class="home-title">[^<]*)</h1>', r'\1</p>', tpl, count=1)
    if cbt_block:
        tpl = tpl.replace(cbt_block, '<div id="cbt-slot" data-src="/sections/cbt26.html"></div>', 1)
    root_m = re.search(r'<div id="subject-content-root">.*?</div></div>', tpl)
    assert root_m, 'subject-content-root 를 찾지 못했습니다.'

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
        desc = clip('정보통신기사 필기 %s과목 %s — %s. %s' % (n, sname, d['title'], d['body']), 150)
        t = set_meta(tpl, d['page_title'], desc, d['url'],
                     [home_crumb, ('%s과목 %s' % (n, sname), '/%s/' % d['sid']), (d['title'], d['url'])],
                     d['title'])
        t = t.replace('<script src="/assets/routes.js"></script>', page_script({'sec': sec}), 1)
        t = t.replace(root_m.group(0), '<div id="subject-content-root">' + as_visible(d['html']) + '</div>', 1)
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
        body = ('<div class="section visible" id="sec-hub-%s">%s<h1 class="section-title">%s과목 %s</h1>'
                '<p class="hub-lead">정보통신기사 필기 %s과목 <b>%s</b>의 핵심 주제 %d개입니다. 주제를 누르면 정리 페이지로 이동합니다.</p>'
                '<ul class="hub-list">%s</ul></div>') % (sid, hub_css, n, esc(sname), n, esc(sname), count, ''.join(lis))
        body = body.replace('<ul class="hub-list"></ul>', '')
        titles = ', '.join(sections[a]['title'] for k, a, _ in side_items.get(sid, []) if k == 'item' and a in sections)
        desc = clip('정보통신기사 필기 %s과목 %s 핵심정리 주제 모음 — %s' % (n, sname, titles), 150)
        t = set_meta(tpl, routes['hub-' + sid][1], desc, url,
                     [home_crumb, ('%s과목 %s' % (n, sname), url)], '%s과목 %s 핵심정리' % (n, sname))
        t = t.replace('<script src="/assets/routes.js"></script>', page_script({'hub': sid}), 1)
        t = t.replace(root_m.group(0), body + root_m.group(0), 1)
        written += wr('%s/index.html' % sid, t, gen)

    # 단독 페이지 (요약 · CBT · 기출)
    for sec, d in extra.items():
        t = set_meta(tpl, d['page_title'], d['desc'], d['url'], [home_crumb, (d['title'], d['url'])], d['title'])
        t = t.replace('<script src="/assets/routes.js"></script>', page_script({'sec': sec}), 1)
        if sec == 'cbt26':
            t = t.replace('<div id="cbt-slot" data-src="/sections/cbt26.html"></div>', as_visible(d['html']), 1)
        else:
            t = t.replace(d['html'], as_visible(d['html']), 1)
        t = mark_active(t, sec)
        written += wr(d['url'].strip('/') + '/index.html', t, gen)

    # ── sitemap.xml ──────────────────────────────────────────
    urls = [('/', git_date('index.html', 'subjects', 'data'), '1.0')]
    for sid in sorted(subj_names):
        f = [d['file'] for d in sections.values() if d['sid'] == sid]
        urls.append(('/%s/' % sid, git_date(*(f or ['index.html'])), '0.8'))
    for sec, d in extra.items():
        urls.append((d['url'], git_date('index.html', 'data') if sec == 'quiz' else git_date('index.html'), '0.8'))
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
