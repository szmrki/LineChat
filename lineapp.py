from flask import Flask, request, abort
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, StickerMessage, 
                            StickerSendMessage, AudioMessage, LocationMessage, ImageSendMessage)
from openai import OpenAI
import os
from dotenv import load_dotenv
import random
from pathlib import Path
import glob
import deepl
from langdetect import detect
import requests
from datetime import datetime, timedelta
import json

app = Flask(__name__)  #flaskのインスタンスを作成
CORS(app)

load_dotenv() #pyenv環境内ででAPIキーを取得するため

#Lineのアクセストークンとシークレットを設定
line_bot_api = LineBotApi(os.environ["LINE_BOT_API"])
handler = WebhookHandler(os.environ["LINE_WEBHOOK_HANDLER"])
package_id_list = [11537, 11538, 11539]  #LINEスタンプ用

# ルートURLへのリクエストを処理する関数
@app.route('/', methods=['GET', 'POST']) #ルートにGETかPOSTでアクセスされたときにhome関数を実行する
def home():
    if request.method == 'POST': #POSTでアクセスされた時のみ以下を実行する
        signature = request.headers['X-Line-Signature'] #署名の検証のため取得
        body = request.get_data(as_text=True) #Webhookからのリクエストの詳細を取得
        
        handler.handle(body, signature)  #イベントに応じた処理を行う
        return 'OK'
    # ページを表示
    return abort(400)

#ユーザーからテキストメッセージが送られてきたときの処理
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    question = event.message.text #ユーザからのメッセージを取得
    # ユーザーからのメッセージに対して応答
    text = generate_response(question)  #応答メッセージの作成
    texts = text.split('\n')     #応答メッセージに改行を含む場合、別の吹き出しとして送信するため分割
    messages = [TextSendMessage(text=texts[i]) for i in range(len(texts))]  #複数メッセージ送信の際はTextSendMessageのリストを渡す
    if len(messages) >= 5:     #複数メッセージの送信数に上限があるため、上限を超える際は一つのメッセージとして送信する
        messages = [TextSendMessage(text=text)]
    choice_stamp(text, messages)
    
    conversation = {"user": question, "assistant": text} #次回の会話の際に使用するために今回の会話を保存
    with open("/tmp/conversation.json", "w") as f:  #/tmpにjsonで保存
        json.dump(conversation, f)
    
    line_bot_api.reply_message(
        event.reply_token,
        messages=messages
    )

#ユーザーからスタンプが送られてきたときの処理、ランダムでスタンプを送信
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    num = random.randint(0, len(package_id_list)-1)
    if num == 0:
        sticker_id = random.randint(52002740, 52002773)
    elif num == 1:
        sticker_id = random.randint(51626494, 51626533)
    else :
        sticker_id = random.randint(52114110, 52114149)
        
    line_bot_api.reply_message(
        event.reply_token,
        #StickerSendMessage(package_id=event.message.package_id,sticker_id=event.message.sticker_id)   オウム返し
        messages=StickerSendMessage(package_id=package_id_list[num], sticker_id=sticker_id)
    )

#ユーザから音声メッセージが送られてきたときの処理
@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id=message_id)  #音声データをバイナリデータとして取得

    audio_data = b''
    for chunk in message_content.iter_content():
        audio_data += chunk
    audio_filename = f'audio_{message_id}.m4a'
    audio_filepath = f'/tmp/{audio_filename}'
    with open(audio_filepath, 'wb') as f:   #Lambda関数の/tmpに一時保存
        f.write(audio_data)

    line_bot_api.reply_message(
        event.reply_token,
        messages=TextSendMessage(text=transcribe_audio(audio_filepath))
    )
    
    # /tmp以下のファイルを全て削除
    for p in glob.glob("/tmp/*"):
       if os.path.isfile(p):
           os.remove(p)

#ユーザから位置情報メッセージが送られたときの処理
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    weather_api_key = os.environ["WEATHER_API_KEY"]
    lat = event.message.latitude
    lon = event.message.longitude
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&APPID={weather_api_key}" #天気予報のurlに接続
    jsondata = requests.get(url).json()

    text = weather_info(event, jsondata)
    icon_url = weather_icon(jsondata)
    line_bot_api.reply_message(
        event.reply_token,
        messages=[TextSendMessage(text=text), ImageSendMessage(original_content_url=icon_url, preview_image_url=icon_url)]
    )

#特定の文言に応じてスタンプを選択する関数
def choice_stamp(text, messages):  
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
def generate_response(question):
    # OpenAI APIキーを設定
    api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)

    messages=[
            {"role":"system", "content": os.environ["CONTENT"]}
        ]
    if os.path.isfile("/tmp/conversation.json"):       #会話記録があれば、それを含めてレスポンスを作成させる
        with open("/tmp/conversation.json", "r") as f:
            past_messages = json.load(f)
        os.remove("/tmp/conversation.json")
        messages.append({"role":"user", "content": past_messages["user"]})
        messages.append({"role":"assistant", "content": past_messages["assistant"]})
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

# メイン関数
if __name__ == '__main__':   #python answer.pyとして実行された場合のみ実行が行われる
    # Flaskアプリケーションを起動
    app.run(debug=True)

