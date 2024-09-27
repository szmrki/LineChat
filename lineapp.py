from flask import Flask, request, abort
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, StickerMessage, 
                            StickerSendMessage, AudioMessage, LocationMessage, ImageSendMessage)
import os
from dotenv import load_dotenv
import glob
import json
import boto3
import functions
from datetime import datetime, timedelta

app = Flask(__name__)  #flaskのインスタンスを作成
CORS(app)

load_dotenv() #pyenv環境内ででAPIキーを取得するため
s3 = boto3.client("s3") 
bucket = "line-bot-data"

#Lineのアクセストークンとシークレットを設定
line_bot_api = LineBotApi(os.environ["LINE_BOT_API"])
handler = WebhookHandler(os.environ["LINE_WEBHOOK_HANDLER"])

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
    functions.show_loading_animation(event) #ローディングアニメーションを表示

    question = event.message.text #ユーザからのメッセージを取得
    # ユーザーからのメッセージに対して応答
    text = functions.generate_response(question, event)
    texts = text.split('\n')     #応答メッセージに改行を含む場合、別の吹き出しとして送信するため分割
    texts = [s for s in texts if s != ''] #空要素があると返信してくれないので削除
    messages = [TextSendMessage(text=texts[i]) for i in range(len(texts))]  #複数メッセージ送信の際はTextSendMessageのリストを渡す
    if len(messages) >= 5:     #複数メッセージの送信数に上限があるため、上限を超える際は一つのメッセージとして送信する
        messages = [TextSendMessage(text=text)]
    functions.choice_stamp(text, messages)
    
    conversation = []
    tmp_path, key_path = functions.make_path(event)
    if functions.check_s3_file_exists(key_path):        #会話履歴があれば読み込む
        conversation = functions.load_conversation(event)
        data_time = datetime.strptime(conversation[len(conversation)-1]["date"], '%y%m%d%H%M%S')
        if data_time + timedelta(minutes=10) < datetime.now():
            conversation.clear()
            s3.delete_object(Bucket=bucket, Key=key_path)

    conversation.append({"user": question, "assistant": text, "date": datetime.now().strftime('%y%m%d%H%M%S')}) #次回の会話の際に使用するために今回の会話を保存
    
    with open(tmp_path, "w") as f:  #/tmpにjsonlで保存したのちにS3に保存
        for obj in conversation:
            json.dump(obj, f, ensure_ascii=False)
            f.write('\n')
    
    s3.upload_file(tmp_path, bucket, key_path) 
    os.remove(tmp_path)

    line_bot_api.reply_message(
        event.reply_token,
        messages=messages
    )

#ユーザーからスタンプが送られてきたときの処理、ランダムでスタンプを送信
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    package_id, sticker_id = functions.random_sticker()
        
    line_bot_api.reply_message(
        event.reply_token,
        #StickerSendMessage(package_id=event.message.package_id,sticker_id=event.message.sticker_id)   オウム返し
        messages=StickerSendMessage(package_id=package_id, sticker_id=sticker_id)
    )

#ユーザから音声メッセージが送られてきたときの処理
@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    functions.show_loading_animation(event) #ローディングアニメーションを表示
    
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
        messages=TextSendMessage(text=functions.transcribe_audio(audio_filepath))
    )
    
    # /tmp以下のファイルを全て削除
    for p in glob.glob("/tmp/*"):
       if os.path.isfile(p):
           os.remove(p)

#ユーザから位置情報メッセージが送られたときの処理
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    text, icon_url = functions.weather_info(event)
    
    line_bot_api.reply_message(
        event.reply_token,
        messages=[TextSendMessage(text=text), ImageSendMessage(original_content_url=icon_url, preview_image_url=icon_url)]
    )

# メイン関数
if __name__ == '__main__':   #python lineapp.pyとして実行された場合のみ実行が行われる
    # Flaskアプリケーションを起動
    app.run(debug=True)