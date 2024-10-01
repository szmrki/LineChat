import random
from linebot.models import StickerSendMessage
import os
import json
from openai import OpenAI
from pathlib import Path
from langdetect import detect
import deepl
from datetime import datetime, timedelta, timezone
import lineapp
from botocore.errorfactory import ClientError
import requests
from dotenv import load_dotenv
import glob

# OpenAI APIキーを設定
load_dotenv()
api_key = os.environ["OPENAI_API_KEY"]
client = OpenAI(api_key=api_key)

#ファインチューニング済みのモデルに質問を送信してレスポンスを取得する関数
def get_response(messages):
    response = client.chat.completions.create(
        model="ft:gpt-4o-mini-2024-07-18:personal::AAGVWuNG",
        messages=messages
    )
    eng_response = response.choices[0].message.content
    return eng_response

# テキストメッセージにおいて質問に対するレスポンスを生成する関数
def generate_response(question, event):
    messages=[{"role":"system", "content": os.environ["CONTENT"]}]
    tmp_path, key_path = make_path(event)
    if check_s3_file_exists(key_path):       #会話記録があれば、それを含めてレスポンスを作成させる
        past_messages = how2use_memory(tmp_path, key_path)
        n = len(past_messages)
        if n > 0:
            if n > 1:
                if n > 2:
                    messages.append({"role":"user", "content": past_messages[n-3]["user"]})
                    messages.append({"role":"assistant", "content": past_messages[n-3]["assistant"]})
                messages.append({"role":"user", "content": past_messages[n-2]["user"]})
                messages.append({"role":"assistant", "content": past_messages[n-2]["assistant"]})
            messages.append({"role":"user", "content": past_messages[n-1]["user"]})
            messages.append({"role":"assistant", "content": past_messages[n-1]["assistant"]})      
    else:
        past_messages = [] 
    messages.append({"role":"user", "content": question})

    return get_response(messages), past_messages

#オーディオファイルの文字起こしをする関数
def transcribe_audio(audio_file):
    
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
def weather_info(event):  
    weather_api_key = os.environ["WEATHER_API_KEY"]
    address = event.message.address
    lat = event.message.latitude
    lon = event.message.longitude
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&APPID={weather_api_key}" #天気予報のurlに接続
    jsondata = requests.get(url).json() 
    
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
    
    #天気のアイコンを取得する
    icon_id = latest["weather"][0]["icon"]
    icon_url = f'https://openweathermap.org/img/wn/{icon_id}@2x.png'
    return text, icon_url

#choice_stamp関数のif文の処理
def choice_sticker_if(text, messages, num, package_id_list, text1, text2, list0, list1, list2):
    if text1 in text or text2 in text:
        if num == 0:
            sticker_id = random.choice(list0)
        elif num == 1:
            sticker_id = random.choice(list1)
        else :
            sticker_id = random.choice(list2)
        messages.append(StickerSendMessage(package_id=package_id_list[num], sticker_id=sticker_id))

#特定の文言に応じてスタンプを選択する関数
def choice_sticker(text, messages):  
    package_id_list = [11537, 11538, 11539]  #LINEスタンプ用
    num = random.randint(0, len(package_id_list)-1)
    choice_sticker_if(text, messages, num, package_id_list, "了解", "おっけー", 
                    [52002735, 52002740], [51626500, 51626501, 51626520], [52114113, 52114117])
    choice_sticker_if(text, messages, num, package_id_list, "泣", "涙",
                    [52002750], 
                    [51626510, 51626522, 51626524, 51626529, 51626531], 
                    [52114126, 52114137, 52114141, 52114145, 52114149])
    choice_sticker_if(text, messages, num, package_id_list, "すき！", "ありがとう！",
                    [52002736, 52002737, 52002742, 52002743, 52002745, 52002747], 
                    [51626495, 51626499, 51626502, 51626509], 
                    [52114111, 52114112, 52114118, 52114119, 52114124, 52114130, 52114147])

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
def load_conversation(tmp_path, key_path):
    lineapp.s3.download_file(lineapp.bucket, key_path, tmp_path)
    with open(tmp_path, "r") as f:
        conversation = [json.loads(l) for l in f.readlines()]
    os.remove(tmp_path)
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

#会話記録をS3に保存する関数
def record_to_s3(tmp_path, key_path, conversation):
    with open(tmp_path, "w") as f:  #/tmpにjsonlで保存したのちにS3に保存
        for obj in conversation:
            json.dump(obj, f, ensure_ascii=False)
            f.write('\n')
    
    lineapp.s3.upload_file(tmp_path, lineapp.bucket, key_path) 
    os.remove(tmp_path)

#/tmp以下のファイルを全て削除する関数
def delete_tmp_all():
    for p in glob.glob("/tmp/*"):
       if os.path.isfile(p):
           os.remove(p)

#LINE上で返信をする関数
def reply_LINE(event, messages):
    lineapp.line_bot_api.reply_message(
        event.reply_token,
        messages=messages
    )

#ファイルの最終更新日時を取得する関数
def get_last_modified(key_path):
    obj = lineapp.s3.list_objects(Bucket=lineapp.bucket, Prefix='text/')
    files = [content['Key'] for content in obj['Contents']]
    lm = [content['LastModified'] for content in obj['Contents']] 
    for i in range(len(files)):
        if files[i] == key_path:
            return lm[i]
    return None

#ファイルの更新日時に応じて記憶の取り扱い方を決める関数
def how2use_memory(tmp_path, key_path):
    #3時間以上経過していれば、記憶を消す
    if get_last_modified(key_path) + timedelta(hours=3) < datetime.now(timezone.utc): 
        lineapp.s3.delete_object(Bucket=lineapp.bucket, Key=key_path)
        conversation = []
    else:
        conversation = load_conversation(tmp_path, key_path) #そうでなければ、記憶を取り出す
        conversation = []
        
    return conversation

#ローディングアニメーションを表示する関数
def show_loading_animation(event):
    url = 'https://api.line.me/v2/bot/chat/loading/start'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {os.environ["LINE_BOT_API"]}'
    }
    payload = {
        "chatId": lineapp.line_bot_api.get_profile(event.source.user_id).user_id,
        "loadingSeconds": 30
    }
    payload = json.dumps(payload)
    requests.post(url, headers=headers, data=payload)

#ブロードキャストメッセージを送信する関数
def send_broadcast_message():
    #url = 'https://api.line.me/v2/bot/message/push'    プッシュメッセージにするときはこっち、payload内にtoを追加
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {os.environ["LINE_BOT_API"]}'
    }
    question_list = ["何か質問して！", "今日は何したの？", "元気が出る一言欲しい！"]
    question = random.choice(question_list)
    messages = [
            {"role":"system", "content": os.environ["CONTENT"]},
            {"role":"user", "content": question}
        ]
    text = get_response(messages)

    #質問と返答を各ファイルに保存
    obj = lineapp.s3.list_objects(Bucket=lineapp.bucket, Prefix='text/') #jsonで返ってくる
    files = [content['Key'] for content in obj['Contents']] #text/のすべてのファイルを取得
    for p in files:
        conversation = how2use_memory("/tmp/conversation_former.jsonl", p)
        conversation.append({"user": question, "assistant": text})
        record_to_s3("/tmp/conversation_later.jsonl", p, conversation)
        delete_tmp_all()
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    payload = json.dumps(payload)
    requests.post(url, headers=headers, data=payload)