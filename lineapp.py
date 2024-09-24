from flask import Flask, request, abort
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerMessage, StickerSendMessage, AudioMessage
from openai import OpenAI
import os
from dotenv import load_dotenv
import random
from pathlib import Path
import glob
import deepl
from langdetect import detect

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
    choice_stamp(text, messages)
    
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
    #url = f'https://api-data.line.me/v2/bot/message/{message_id}/content'
    message_content = line_bot_api.get_message_content(message_id=message_id)  #音声データをバイナリデータとして取得
    audio_data = b''
    for chunk in message_content.iter_content():
        audio_data += chunk
    
    audio_filename = f'audio_{message_id}.m4a'
    with open(f'/tmp/{audio_filename}', 'wb') as f:   #Lambda関数の/tmpに一時保存
        f.write(audio_data)

    line_bot_api.reply_message(
        event.reply_token,
        messages=TextSendMessage(text=transcribe_audio(f'/tmp/{audio_filename}'))
    )
    
    # 一時ディレクトリ配下のファイルを全て削除
    for p in glob.glob("/tmp/*"):
       if os.path.isfile(p):
           os.remove(p)
    
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
    
    # ファンチューニング済みのモデルに質問を送信してレスポンスを取得
    response = client.chat.completions.create(
        model="ft:gpt-4o-mini-2024-07-18:personal::AAGVWuNG",
        messages=[
            {"role":"system", "content": os.environ["CONTENT"]},
            {"role":"user", "content": question}
            ],
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

    if detect(transcription) != 'ja':
        deepl_api_key = os.environ["DEEPL_API_KEY"]
        translator = deepl.Translator(deepl_api_key)
        transcription = translator.translate_text(transcription, target_lang='JA').text
    
    return transcription

# メイン関数
if __name__ == '__main__':   #python answer.pyとして実行された場合のみ実行が行われる
    # Flaskアプリケーションを起動
    app.run(debug=True)

