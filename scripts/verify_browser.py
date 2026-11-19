"""Exercise the built Vue app and capture submission evidence using the installed Edge browser."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

import requests
from playwright.sync_api import expect, sync_playwright


def serve(folder):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    environment = {**os.environ, 'DATABASE_PATH': str(Path(folder) / 'browser.sqlite3'),
                   'TOUR_API_KEY': '', 'TMAP_APP_KEY': '', 'GMS_KEY': '', 'LOGGING_ENABLED': 'true'}
    args = [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(port)]
    process = subprocess.Popen(args, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    url = f'http://127.0.0.1:{port}'
    deadline = monotonic() + 20
    while monotonic() < deadline and process.poll() is None:
        try:
            if requests.get(url, timeout=1).ok:
                return process, url
        except requests.RequestException:
            pass
        sleep(.15)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError('Built frontend did not start. Run npm run build first.')


def verify(url, output):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1010}, device_scale_factor=1, locale='ko-KR')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def shot(name, full=False):
            page.screenshot(path=output / f'{name}.png', full_page=full, animations='disabled')

        def button(name):
            return page.get_by_role('button', name=name, exact=True)

        def send(message):
            field = page.get_by_role('textbox', name='크리스마스 계획 메시지')
            field.fill(message)
            field.press('Enter')

        page.goto(url)
        expect(page.get_by_role('heading', name='메리와 대화')).to_be_visible()
        shot('01-chat', True)
        page.get_by_role('button', name='예시 초대장 받아보기').click()
        expect(page.get_by_text('시연 모드', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='초대장이 도착했어요 봉투 열기')).to_be_visible(timeout=15000)
        page.get_by_role('button', name='초대장이 도착했어요 봉투 열기').click()
        expect(page.get_by_role('dialog', name='크리스마스 초대장')).to_be_visible()
        expect(page.get_by_role('img', name='방문 순서와 경로를 좌표에 표시한 지도')).to_be_visible()
        expect(page.get_by_role('heading', name='오늘의 음악')).to_be_visible()
        page.get_by_role('dialog').screenshot(path=output / '02-invitation.png', animations='disabled')
        button('초대장 저장').click()
        expect(page.get_by_text('초대장 보관함에 넣었어요.')).to_be_visible()
        button('닫기').click()

        send('같은 조건에서 도보는 10분 이내로 바꿔 줘.')
        page.get_by_role('button', name='초대장이 도착했어요 봉투 열기').click(timeout=15000)
        expect(page.get_by_role('heading', name='눈꽃 다과점')).to_be_visible()
        button('초대장 저장').click()
        expect(page.get_by_text('시간이 겹치는 초대장')).to_be_visible()
        page.keyboard.press('Escape')
        button('초대장 보관함').click()
        expect(page.get_by_role('heading', name='초대장 보관함')).to_be_visible()
        page.locator('.list-item').first.click()
        expect(page.get_by_text('시간이 겹치는 초대장')).to_be_visible()
        shot('03-archive', True)
        button('일정 수정').click()
        page.get_by_label('제목', exact=True).fill('내가 수정한 겨울 편지')
        page.get_by_label('시작', exact=True).fill('15:00')
        button('변경 저장').click()
        expect(page.get_by_role('heading', name='내가 수정한 겨울 편지')).to_be_visible()
        expect(page.get_by_text('경로와 이용 조건을 다시 확인해야 하는 일정이에요.')).to_be_visible()
        button('삭제').click()
        button('삭제 확인').click()
        expect(page.locator('.list-item')).to_have_count(1)

        button('실행 기록').click()
        page.locator('.list-item').first.click()
        expect(page.get_by_role('heading', name='실행 기록 상세')).to_be_visible()
        replan = page.get_by_text('재계획 · 대안 탐색').first
        expect(replan).to_be_visible()
        replan.scroll_into_view_if_needed()
        shot('04-replan')
        page.evaluate('window.scrollTo(0, 0)')
        shot('05-logs')
        button('기록 삭제').click()
        button('삭제 확인').click()
        expect(page.get_by_text('저장된 기록이 없어요.')).to_be_visible()
        assert not errors, errors

        page.goto(url + '/docs')
        expect(page.get_by_text('Dear. Me API', exact=False).first).to_be_visible(timeout=15000)
        shot('06-api', True)

        mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1, is_mobile=True,
                                  has_touch=True, locale='ko-KR')
        mobile.goto(url)
        expect(mobile.get_by_role('heading', name='메리와 대화')).to_be_visible()
        assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        mobile.screenshot(path=output / '07-mobile.png', full_page=True, animations='disabled')

        page.goto(url)
        page.route('**/api/chat/*', lambda route: (sleep(.5), route.continue_()))
        send('크리스마스에 종로에서 14:00부터 18:00까지 전시와 카페를 가고 싶어.')
        expect(page.get_by_role('status').filter(has_text='중')).to_be_visible()
        expect(page.get_by_role('log').get_by_text(
            '어느 역 근처로 찾아볼까? 강남역처럼 역 이름을 알려줘.')).to_be_visible()
        send('종로3가역')
        expect(page.get_by_role('log').get_by_text(
            '역 위치를 확인하지 못했어. 잠시 후 다시 시도해 줘.')).to_be_visible()
        page.get_by_text('확인할 내용', exact=False).last.click()
        expect(page.get_by_text('서버 환경변수에 공급자 API 키를 설정해 주세요.', exact=False).first).to_be_visible()
        shot('08-missing-key', True)
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', type=Path, default=Path('docs/evidence/screens'))
    arguments = parser.parse_args()
    arguments.export.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as folder:
        process, url = serve(folder)
        try:
            verify(url, arguments.export)
        finally:
            process.terminate()
            process.wait(timeout=10)
    print('PASS: Chrome-compatible Edge desktop/mobile, chat, invitation, overlaps, editing, deletion, logs, Swagger.')
