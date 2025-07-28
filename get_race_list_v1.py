import requests
from bs4 import BeautifulSoup
import time
import json
import datetime
import random

# リトライ付きリクエスト関数（timeout=(5,30), 最大5回リトライ）
def safe_request(url, retries=5, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=(5, 30))  # 接続5秒、応答30秒
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response
        except requests.exceptions.RequestException as e:
            print(f"[{attempt+1}/{retries}] リクエスト失敗: {e} URL={url}")
            if attempt < retries - 1:
                time.sleep(delay + random.uniform(0, 1))  # リトライ間隔を少しランダム化
    return None

def get_racelist_details(date_str, place_code, race_num):
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_num}&jcd={place_code}&hd={date_str}"
    racers_data = []
    response = safe_request(url)
    if not response:
        print(f"出走表データ取得に失敗しました: {date_str} {place_code} {race_num}R")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('div', class_='table1 is-tableFixed__3rdadd')
    if not table:
        print(f"出走表テーブルが見つかりません: {date_str} {place_code} {race_num}R")
        return []

    racer_rows = table.find_all('tbody')
    for row in racer_rows:
        if not row.find('td'):
            continue

        racer = {}
        waku_tag = row.select_one('td[class*="is-boatColor"]')
        racer['waku'] = waku_tag.text.strip() if waku_tag else ''

        name_div = row.find('div', class_='is-fs18')
        racer['name'] = name_div.text.strip() if name_div else ''

        id_class_div = row.find('div', class_='is-fs11')
        if id_class_div:
            raw_text = id_class_div.get_text(separator=' ', strip=True)
            parts = raw_text.split('/')
            if len(parts) > 0:
                racer['id'] = parts[0].strip()
            if len(parts) > 1:
                racer['class'] = parts[1].strip()

        details = row.find_all('td', class_='is-lineH2')
        if len(details) == 5:
            racer['F_L_ST'] = ' / '.join(details[0].stripped_strings)
            racer['national_rate'] = ' / '.join(details[1].stripped_strings)
            racer['local_rate'] = ' / '.join(details[2].stripped_strings)
            racer['motor'] = ' / '.join(details[3].stripped_strings)
            racer['boat'] = ' / '.join(details[4].stripped_strings)

        if racer.get('name'):
            racers_data.append(racer)

    return racers_data

def get_races_for_place(date_str, place_code):
    url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={place_code}&hd={date_str}"
    response = safe_request(url)
    if not response:
        print(f"レース番号取得失敗: {date_str} {place_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    race_num_list = []
    table = soup.find('div', class_='table1')
    if table:
        races = table.find_all('tbody')
        for race in races:
            race_num_tag = race.find('td', class_='is-fBold')
            if race_num_tag and race_num_tag.find('a'):
                race_num = race_num_tag.find('a').text.strip().replace('R', '')
                race_num_list.append(race_num)
    else:
        print(f"レース番号テーブルが見つかりません: {date_str} {place_code}")

    return race_num_list

def get_race_list_for_date(date_str):
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
    response = safe_request(url)
    if not response:
        print(f"レース場リスト取得失敗: {date_str}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    race_list = []
    table = soup.find('div', class_='table1')
    if table:
        active_places = table.find_all('tbody')
        for place in active_places:
            place_name_tag = place.find('img')
            place_name = place_name_tag['alt'] if place_name_tag else ''
            link_tag = place.find('a', href=lambda href: href and 'raceindex' in href)
            if link_tag and 'jcd=' in link_tag['href']:
                href = link_tag['href']
                place_code = href.split('jcd=')[1].split('&')[0]
                race_list.append({'date': date_str, 'place_code': place_code, 'place_name': place_name})
    else:
        print(f"レース場テーブルが見つかりません: {date_str}")

    return race_list

if __name__ == '__main__':
    # 当日の日付
    today = datetime.datetime.now().strftime('%Y%m%d')
    print(f"\n### {today} のレース一覧を取得します…")

    all_races_data = []
    places = get_race_list_for_date(today)

    if not places:
        print("  レース場が見つかりませんでした。")
    else:
        print(f"  合計 {len(places)} レース場が見つかりました。")
        for place in places:
            print(f"  {place['place_name']} のレース情報を取得中…")
            race_nums = get_races_for_place(today, place['place_code'])
            if not race_nums:
                print(f"    レースが見つかりません: {place['place_name']}")
                continue

            for race_num in race_nums:
                print(f"    {race_num}R の出走表データを取得中…")
                racers = get_racelist_details(today, place['place_code'], race_num)

                if not racers:
                    print(f"    {race_num}R の出走表データが取得できませんでした。スキップします。")
                    continue

                race_info = {
                    'date'      : today,
                    'place_code': place['place_code'],
                    'place_name': place['place_name'],
                    'race_num'  : race_num,
                    'racers'    : racers
                }
                all_races_data.append(race_info)

                # サーバーへの負荷軽減
                time.sleep(1 + random.uniform(0, 0.5))

        # 当日分だけ保存
        with open(f"race_data_{today}.json", 'w', encoding='utf-8') as f:
            json.dump(all_races_data, f, indent=2, ensure_ascii=False)
        print(f"  {today} のデータを race_data_{today}.json に保存しました。")

    print("\n当日のデータ保存が完了しました。")
