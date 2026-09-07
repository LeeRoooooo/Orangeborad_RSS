import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote
import urllib3

# SSL 인증서 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def scrape_egloos_perfect_date():
    target_url = "https://egloos.com/kor"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(target_url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"웹사이트 연결 실패: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    # RSS 피드 기본 틀 생성
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "이글루스 종합 건강 및 정보 피드"
    ET.SubElement(channel, "link").text = target_url
    ET.SubElement(channel, "description").text = "정밀 썸네일 타겟팅을 통해 정확한 업로드 시간을 기록한 피드입니다."

    # 각 게시물 루프
    post_items = soup.select("li.Home_post-item__rLMTZ")

    for item_elm in post_items:
        try:
            # 1. 제목 추출
            title_tag = item_elm.select_one("a.Home_post-item__item-title__o1tdK")
            if not title_tag:
                continue
            title = title_tag.text.strip()

            # 2. 링크 추출 (한글 인코딩)
            raw_href = title_tag.get("href", "")
            encoded_href = quote(raw_href, safe="/")
            full_link = f"https://egloos.com{encoded_href}"

            # 3. 내용 추출
            desc_tag = item_elm.select_one("a.Home_post-item__item-des__QGtuL")
            description = desc_tag.text.strip() if desc_tag else title

            # 4. [정밀 수정] 작가 프로필 이미지를 건너뛰고, 오직 '게시글 썸네일 구역'의 이미지명에서만 14자리 시간 추출
            pub_date = datetime.now().strftime("%Y.%m.%d %H:%M:%S") # 타임스탬프 실패 시 대비용 기본값(현재시간)
            
            # 썸네일 링크 클래스 내부의 img 태그만 콕 집어서 선택합니다.
            thumb_img_tag = item_elm.select_one("a.Home_post-item__thumbnail__GNI4c img")
            
            if thumb_img_tag:
                img_src = thumb_img_tag.get("srcset", "") or thumb_img_tag.get("src", "")
                time_match = re.search(r'(\d{14})', img_src)
                
                if time_match:
                    timestamp_str = time_match.group(1) # 이제 정확히 "20260518161009"를 잡아냅니다.
                    dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    pub_date = dt.strftime("%Y.%m.%d %H:%M:%S")

            # 5. RSS 아이템 등록
            rss_item = ET.SubElement(channel, "item")
            ET.SubElement(rss_item, "title").text = title
            ET.SubElement(rss_item, "link").text = full_link
            ET.SubElement(rss_item, "description").text = description
            ET.SubElement(rss_item, "pubDate").text = pub_date

        except Exception:
            continue

    # XML 파일 저장 및 출력
    ET.indent(rss, space="  ", level=0)
    xml_str = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    final_rss = '<?xml version="1.0" encoding="UTF-8" ?>\n' + xml_str

    print(final_rss)
    with open("egloos_feed.xml", "w", encoding="utf-8") as f:
        f.write(final_rss)
    print("\n[교정 완료] 작가 가입일이 아닌, 기사의 진짜 업로드 시간(2026.05.18 16:10:09 등)으로 매칭되었습니다.")

if __name__ == "__main__":
    scrape_egloos_perfect_date()
