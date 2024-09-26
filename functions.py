import random
from linebot.models import StickerSendMessage
import os
import json
from openai import OpenAI
from pathlib import Path
from langdetect import detect
import deepl
from datetime import datetime, timedelta
import lineapp
from botocore.errorfactory import ClientError

#特定の文言に応じてスタンプを選択する関数
def choice_stamp(text, messages):  
    package_id_list = [11537, 11538, 11539]  #LINEスタンプ用
    num = random.randint(0, len(package_id_list)-1)
    if "了解" in text or "おっけー" in text:   
        if num == 0:
            sticker_ok = random.choice([52002735, 52002740])
        elif num == 1:
            sticker_ok = random.choice([51626500, 51626501, 51626520])
        else :
            sticker_ok = random.choice([52114113, 52114117])
        messages.append(StickerSendMessage(package_id=package_id_list[num], sticker_id=sticker_ok)) #テキストとスタンプの同時送信のために、まとめてリストで渡す
    if "泣" in text or "涙" in text:
        if num == 0:
            sticker_sad = 52002750
        elif num == 1:
            sticker_sad = random.choice([51626510, 51626522, 51626524, 51626529, 51626531])
        else :
            sticker_sad = random.choice([52114126, 52114137, 52114141, 52114145, 52114149])
        messages.append(StickerSendMessage(package_id=package_id_list[num], sticker_id=sticker_sad))
    if "すき！" in text or "ありがとう！" in text:
        if num == 0:
            sticker_love = random.choice([52002736, 52002737, 52002742, 52002743, 52002745, 52002747])
        elif num == 1:
            sticker_love = random.choice([51626495, 51626499, 51626502, 51626509])
        else :
            sticker_love = random.choice([52114111, 52114112, 52114118, 52114119, 52114124, 52114130, 52114147])
        messages.append(StickerSendMessage(package_id=package_id_list[num], sticker_id=sticker_love))

# 質問に対するレスポンスを生成する関数
def generate_response(question, event):
    # OpenAI APIキーを設定
    api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)

    messages=[{"role":"system", "content": os.environ["CONTENT"]}]
    tmp_path, key_path = make_path(event)
    if check_s3_file_exists(key_path):       #会話記録があれば、それを含めてレスポンスを作成させる
        past_messages = load_conversation(event)
        os.remove(tmp_path)

        n = len(past_messages) - 1
        if n > 0:
            if n > 1:
                messages.append({"role":"user", "content": past_messages[n-2]["user"]})
                messages.append({"role":"assistant", "content": past_messages[n-2]["assistant"]})
            messages.append({"role":"user", "content": past_messages[n-1]["user"]})
            messages.append({"role":"assistant", "content": past_messages[n-1]["assistant"]})
        messages.append({"role":"user", "content": past_messages[n]["user"]})
        messages.append({"role":"assistant", "content": past_messages[n]["assistant"]})
    messages.append({"role":"user", "content": question})

    # ファンチューニング済みのモデルに質問を送信してレスポンスを取得
    response = client.chat.completions.create(
        model="ft:gpt-4o-mini-2024-07-18:personal::AAGVWuNG",
        messages=messages
    #max_tokens=50
    )
    eng_response = response.choices[0].message.content
    return eng_response

#オーディオファイルの文字起こしをする関数
def transcribe_audio(audio_file):
    # OpenAI APIキーを設定
    api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)
    
    #文字起こしを行う
    transcription = client.audio.transcriptions.create(
    model="whisper-1", 
    file=Path(audio_file), 
    response_format="text"
    )
    transcription = transcription.replace('\n', '')

    if detect(transcription) != 'ja':     #日本語ではないと判断されたとき、DeepLで翻訳を行う
        deepl_api_key = os.environ["DEEPL_API_KEY"]
        translator = deepl.Translator(deepl_api_key)
        transcription = translator.translate_text(transcription, target_lang='JA').text
    
    return transcription

#緯度・経度を基に天気予報を作成する関数
def weather_info(event, jsondata):   
    address = event.message.address
    jst = datetime.strptime(jsondata["list"][0]["dt_txt"], '%Y-%m-%d %H:%M:%S')+timedelta(hours=9)  #UTCからJSTに変換
    jst = jst.strftime('%Y-%m-%d %H:%M')
    latest = jsondata["list"][0]
    #風向を方位角をもとに決める
    deg = latest["wind"]["deg"]
    if 0 <= deg and deg < 22.5:
        wind_dir = "北"
    elif 22.5 <= deg and deg < 67.5:
        wind_dir = "北東"
    elif 67.5 <= deg and deg < 112.5:
        wind_dir = "東"
    elif 112.5 <= deg and deg < 157.5:
        wind_dir = "南東"
    elif 157.5 <= deg and deg < 202.5:
        wind_dir = "南"
    elif 202.5 <= deg and deg < 247.5:
        wind_dir = "南西"
    elif 247.5 <= deg and deg < 292.5:
        wind_dir = "西"
    elif 292.5 <= deg and deg < 337.5:
        wind_dir = "北西"
    else:
        wind_dir = "北"
    text = (f'{address}付近の天気\n日時: {jst}\n'
            f'気温: {round(latest["main"]["temp"], 1)}℃\n'
            f'湿度: {latest["main"]["humidity"]}%\n'
            f'降水確率: {round(latest["pop"]*100)}%\n'
            f'風速: {round(latest["wind"]["speed"], 1)}m/s\n'
            f'風向: {wind_dir}')
    return text

#天気のアイコン画像を取得する関数
def weather_icon(jsondata):
    icon_id = jsondata["list"][0]["weather"][0]["icon"]
    icon_url = f'https://openweathermap.org/img/wn/{icon_id}@2x.png'
    return icon_url

#ランダムにスタンプを決める関数
def random_sticker():
    package_id_list = [11537, 11538, 11539]  #LINEスタンプ用
    num = random.randint(0, len(package_id_list)-1)
    if num == 0:
        sticker_id = random.randint(52002740, 52002773)
    elif num == 1:
        sticker_id = random.randint(51626494, 51626533)
    else :
        sticker_id = random.randint(52114110, 52114149)
    package_id = package_id_list[num]
    return package_id, sticker_id

#S3に会話データが保存されているか確認する関数
def check_s3_file_exists(key):
    try:
        lineapp.s3.head_object(Bucket=lineapp.bucket, Key=key)
        return True
    except ClientError:
        return False
    
#会話データを読み込む関数
def load_conversation(event):
    tmp_path, key_path = make_path(event)
    lineapp.s3.download_file(lineapp.bucket, key_path, tmp_path)
    with open(tmp_path, "r") as f:
        conversation = [json.loads(l) for l in f.readlines()]
    return conversation

#User IDをもとにパスを作成する関数
def make_path(event):
    user_id = lineapp.line_bot_api.get_profile(event.source.user_id).user_id
    user_id = h(user_id)
    tmp_path = f"/tmp/conversation_{user_id}.jsonl"
    key_path = f"text/conversation_{user_id}.jsonl"
    return tmp_path, key_path

#ハッシュ関数
def h(x):
    y = 0
    for i in range(len(x)):
        y += ord(x[i])
    return y % 4239047233139  #割る数が何であれば適切かはわかっていない