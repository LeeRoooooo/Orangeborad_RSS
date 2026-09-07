import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from feedgen.feed import FeedGenerator
from playwright.async_api import async_playwright

BASE_URL = "https://orangeboard.co.kr"
TARGET_URL = "https://orangeboard.co.kr/reports?srt=rct"

KST = timezone(timedelta(hours=9))


async def scrape_reports(page):
    print("🔎 오렌지보드 최신 리포트 탐색 중...")
    try:
        # User-Agent 설정 및 접속 대기
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=90000)

        # 리포트 링크 로딩 대기
        await page.wait_for_selector(
            "a[href*='/@']", state="attached", timeout=30000
        )
    except Exception as e:
        print(f"⚠️ 페이지 로딩 타임아웃 경고: {e}")

    reports_data = await page.evaluate(
        """() => {
        const results = [];
        const allLinks = Array.from(document.querySelectorAll("a[href*='/@']"));
        const articleLinks = allLinks.filter(a => {
            const href = a.getAttribute('href') || '';
            return /^\\/@[^\\/]+\\/.+/.test(href);
        });

        articleLinks.forEach(link => {
            const href = link.getAttribute('href') || '';
            if (!href) return;

            const h5 = link.querySelector("h5");
            const title = h5 ? h5.innerText.trim() : link.innerText.trim();
            if (!title) return;

            const matchUser = href.match(/^\\/@([^\\/]+)/);
            let authorId = matchUser ? matchUser[1] : '';

            let row = link.parentElement;
            for (let i = 0; i < 6; i++) {
                if (row && row.parentElement && row.parentElement !== document.body) {
                    if (/\\d{4}[-.]\\d{2}[-.]\\d{2}/.test(row.innerText)) {
                        break;
                    }
                    row = row.parentElement;
                }
            }

            let authorName = '';
            if (row) {
                const authorLink = row.querySelector(`a[href='/@${authorId}']`);
                if (authorLink) {
                    authorName = authorLink.innerText.trim();
                }
            }
            const author = authorName || authorId;

            let dateStr = '';
            if (row) {
                const dateMatch = row.innerText.match(/\\b(\\d{4})[-.](\\d{2})[-.](\\d{2})\\b/);
                if (dateMatch) {
                    dateStr = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
                }
            }

            const rect = link.getBoundingClientRect();
            const topPos = rect.top + window.scrollY;

            results.push({
                href: href,
                title: title,
                author: author,
                date: dateStr,
                top: topPos
            });
        });

        return results;
    }"""
    )

    seen = set()
    entries = []
    for item in reports_data:
        if item["href"] not in seen:
            seen.add(item["href"])
            full_link = urljoin(BASE_URL, item["href"])
            date_val = (
                item["date"]
                if item["date"]
                else datetime.now(KST).strftime("%Y-%m-%d")
            )

            entries.append(
                {
                    "title": item["title"],
                    "author": item["author"],
                    "link": full_link,
                    "date": date_val,
                    "top": item["top"],
                }
            )

    return entries


async def main():
    async with async_playwright() as p:
        # 리눅스 환경 최적화 브라우저 옵션
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        entries = await scrape_reports(page)
        await browser.close()

        if not entries:
            print("⚠️ 수집된 항목이 없습니다.")
            return

        # 최신 글 1등 배치 (역순 뒤집기)
        entries.reverse()

        fg = FeedGenerator()
        fg.title("오렌지보드 최신 리포트 피드")
        fg.link(href=TARGET_URL, rel="alternate")
        fg.description("오렌지보드 최신 리포트 실시간 RSS")
        fg.language("ko")

        now = datetime.now(KST)

        for idx, item in enumerate(entries[:40]):
            fe = fg.add_entry()
            fe.id(item["link"])

            author_prefix = f"[{item['author']}] " if item["author"] else ""
            display_date = item["date"].replace("-", ".")
            fe.title(f"{author_prefix}{item['title']} ({display_date})")

            fe.link(href=item["link"])
            fe.description(
                f"작성자: {item['author']}<br/>날짜: {display_date}<br/><a href='{item['link']}'>원문 보기</a>"
            )

            item_pub_date = now - timedelta(minutes=idx)
            fe.pubDate(item_pub_date)

        output_file = "orangeboard_reports.xml"
        fg.rss_file(output_file, pretty=True)
        print(f"✨ 완료: {output_file} (총 {len(entries)}건 생성)")


if __name__ == "__main__":
    asyncio.run(main())
