import requests
from bs4 import BeautifulSoup
import time
import json
import datetime


def get_racelist_details(date_str: str, place_code: str, race_num: str) -> list[dict]:
    """
    指定されたレースの出走表詳細データを取得する
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_num}&jcd={place_code}&hd={date_str}"
    racers_data = []

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("div", class_="table1 is-tableFixed__3rdadd")
        if not table:
            print(f"出走表テーブルなし: {date_str} {place_code} {race_num}R")
            return []

        for tbody in table.find_all("tbody"):
            if not tbody.find("td"):
                continue

            racer = {}
            waku_tag = tbody.select_one('td[class*="is-boatColor"]')
            racer["waku"] = waku_tag.text.strip() if waku_tag else ""

            name_div = tbody.find("div", class_="is-fs18")
            racer["name"] = name_div.text.strip() if name_div else ""

            id_class_div = tbody.find("div", class_="is-fs11")
            if id_class_div:
                raw = id_class_div.get_text(" ", strip=True)
                parts = raw.split("/")
                racer["id"] = parts[0].strip() if parts else ""
                if len(parts) > 1:
                    racer["class"] = parts[1].strip()

            details = tbody.find_all("td", class_="is-lineH2")
            if len(details) == 5:
                racer["F_L_ST"] = " / ".join(details[0].stripped_strings)
                racer["national_rate"] = " / ".join(details[1].stripped_strings)
                racer["local_rate"] = " / ".join(details[2].stripped_strings)
                racer["motor"] = " / ".join(details[3].stripped_strings)
                racer["boat"] = " / ".join(details[4].stripped_strings)

            if racer.get("name"):
                racers_data.append(racer)

    except requests.exceptions.RequestException as e:
        print(f"出走表取得エラー: {e}")

    return racers_data


def get_races_for_place(date_str: str, place_code: str) -> list[str]:
    """
    その日・その場で開催されるレース番号一覧を取得
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={place_code}&hd={date_str}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        race_nums = []
        table = soup.find("div", class_="table1")
        if table:
            for tbody in table.find_all("tbody"):
                num_tag = tbody.find("td", class_="is-fBold")
                if num_tag and num_tag.find("a"):
                    race_nums.append(num_tag.find("a").text.strip().replace("R", ""))
        return race_nums
    except requests.exceptions.RequestException as e:
        print(f"レース番号取得エラー: {e}")
        return []


def get_race_places_for_date(date_str: str) -> list[dict]:
    """
    その日に開催しているレース場一覧を取得
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        places = []
        table = soup.find("div", class_="table1")
        if table:
            for tbody in table.find_all("tbody"):
                place_img = tbody.find("img")
                place_name = place_img["alt"] if place_img else ""
                link = tbody.find("a", href=lambda h: h and "raceindex" in h)
                if link:
                    place_code = link["href"].split("jcd=")[1].split("&")[0]
                    places.append({"place_code": place_code, "place_name": place_name})
        return places
    except requests.exceptions.RequestException as e:
        print(f"開催レース場取得エラー: {e}")
        return []


if __name__ == "__main__":
    # 日本時間 “今日” を YYYYMMDD 形式で取得
    JST = datetime.timezone(datetime.timedelta(hours=9))
    target_date = datetime.datetime.now(JST).strftime("%Y%m%d")

    print(f"=== {target_date} 開催分の出走表データ取得を開始 ===")
    all_races_data = []

    places = get_race_places_for_date(target_date)
    if not places:
        print("本日は開催しているレース場がありません。")
        exit()

    print(f"開催レース場数: {len(places)} 箇所\n")

    for place in places:
        print(f"[{place['place_name']}] レース一覧取得中…")
        race_nums = get_races_for_place(target_date, place["place_code"])
        for race_num in race_nums:
            print(f"  {race_num}R 出走表取得中…")
            racers = get_racelist_details(target_date, place["place_code"], race_num)

            all_races_data.append(
                {
                    "date": target_date,
                    "place_code": place["place_code"],
                    "place_name": place["place_name"],
                    "race_num": race_num,
                    "racers": racers,
                }
            )
            time.sleep(1)  # サーバー負荷軽減

    # JSON ファイル出力
    out_file = f"race_data_{target_date}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_races_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {out_file} に保存完了（合計 {len(all_races_data)} レース）")
