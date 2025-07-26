import requests
from bs4 import BeautifulSoup
import time
import json
import datetime


def get_racelist_details(date_str, place_code, race_num):
    """
    指定されたレースの出走表詳細データを取得する関数
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_num}&jcd={place_code}&hd={date_str}"
    racers_data = []
    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('div', class_='table1 is-tableFixed__3rdadd')
        if not table:
            print(f"出走表のテーブルが見つかりませんでした: {date_str} {place_code} {race_num}R")
            return []

        racer_rows = table.find_all('tbody')
        for row in racer_rows:
            if not row.find('td'): continue

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

    except requests.exceptions.RequestException as e:
        print(f"出走表データの取得中にエラーが発生しました: {e}")

    return racers_data

def get_races_for_place(date_str, place_code):
    url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={place_code}&hd={date_str}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
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
        return race_num_list
    except requests.exceptions.RequestException as e:
        print(f"レース番号の取得中にエラーが発生しました: {e}")
        return []

def get_race_list_for_date(date_str):
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        race_list = []
        table = soup.find('div', class_='table1')
        if table:
            active_places = table.find_all('tbody')
            for place in active_places:
                place_name_tag = place.find('img')
                place_name = place_name_tag['alt'] if place_name_tag else ''
                link_tag = place.find('a', href=lambda href: href and 'raceindex' in href)
                if link_tag:
                    href = link_tag['href']
                    place_code = href.split('jcd=')[1].split('&')[0]
                    race_list.append({'date': date_str, 'place_code': place_code, 'place_name': place_name})
        return race_list
    except requests.exceptions.RequestException as e:
        print(f"エラーが発生しました: {e}")
        return None

def daterange(start_date, end_date):
    """start_date から end_date までの日付を 1日ずつ返すジェネレータ"""
    for n in range((end_date - start_date).days + 1):
        yield start_date + datetime.timedelta(days=n)

if __name__ == '__main__':
    # 取得開始日・終了日を datetime で定義
    start_date = datetime.datetime.strptime('20240727', '%Y%m%d')
    end_date   = datetime.datetime.strptime('20250726', '%Y%m%d')

    all_races_data = []

    for single_date in daterange(start_date, end_date):
        target_date = single_date.strftime('%Y%m%d')
        print(f"\n### {target_date} のレース一覧を取得します…")
        places = get_race_list_for_date(target_date)

        if not places:
            print("  レース場が見つかりませんでした。")
            continue

        print(f"  合計 {len(places)} レース場が見つかりました。")
        for place in places:
            print(f"  {place['place_name']} のレース情報を取得中…")
            race_nums = get_races_for_place(target_date, place['place_code'])
            for race_num in race_nums:
                print(f"    {race_num}R の出走表データを取得中…")
                racers = get_racelist_details(target_date, place['place_code'], race_num)

                race_info = {
                    'date'      : target_date,
                    'place_code': place['place_code'],
                    'place_name': place['place_name'],
                    'race_num'  : race_num,
                    'racers'    : racers
                }
                all_races_data.append(race_info)

                time.sleep(1)  # サーバーへの負荷軽減

        # 日ごとに別ファイルで保存したい場合はここで書き出し
        with open(f"race_data_{target_date}.json", 'w', encoding='utf-8') as f:
            json.dump([d for d in all_races_data if d['date'] == target_date],
                      f, indent=2, ensure_ascii=False)
        print(f"  {target_date} のデータを race_data_{target_date}.json に保存しました。")

    # 全期間をまとめて１ファイルにしたいなら、ループの外でまとめて保存
    with open("race_data_20240727-20250726.json", 'w', encoding='utf-8') as f:
        json.dump(all_races_data, f, indent=2, ensure_ascii=False)
    print("\n全期間のデータ保存が完了しました。")