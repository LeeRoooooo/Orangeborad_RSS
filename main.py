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
    await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

    await page.wait_for_selector(
        "a[href*='/@'] h5, h5", state="visible", timeout=20000
    )

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
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        entries = await scrape_reports(page)
        await browser.close()

        if not entries:
            print("⚠️ 수집된 항목이 없습니다.")
            return

        # [수정] 복잡한 정렬 대신, 방금 거꾸로 나왔던 순서를 그대로 180도 뒤집어서 최신순으로 교정
        entries.reverse()

        fg = FeedGenerator()
        fg.title("오렌지보드 최신 리포트 피드")
        fg.link(href=TARGET_URL, rel="alternate")
        fg.description("오렌지보드 최신 리포트 실시간 RSS")
        fg.language("ko")

        now = datetime.now(KST)

        # 1등(원자력 발전...)이 가장 최신 시간(now), 아래로 갈수록 1분씩 과거 시간
        for idx, item in enumerate(entries[:40]):
            fe = fg.add_entry()
            fe.id(item["link"])

            # 형식: [작성자] 제목 (날짜)
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
        print(f"✨ 완료: {output_file} (최신 글 1등 배치 성공)")


if __name__ == "__main__":
    asyncio.run(main())
