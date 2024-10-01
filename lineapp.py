from flask import Flask, request, abort
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, StickerMessage, 
                            StickerSendMessage, AudioMessage, LocationMessage, ImageSendMessage,
                            PostbackAction, PostbackEvent, QuickReply, QuickReplyButton)
import os
from dotenv import load_dotenv
import boto3
import functions

app = Flask(__name__)  #flaskのインスタンスを作成
CORS(app)

load_dotenv() #pyenv環境内でAPIキーを取得するため
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

#ポストバックイベント時の処理
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data == "delete":
        functions.reply_LINE(event, TextSendMessage(text="うわぁぁぁぁぁ\n\n何も覚えていない…"))
        key_path = functions.make_path(event)[1]
        if functions.check_s3_file_exists(key_path):
            s3.delete_object(Bucket=bucket, Key=key_path)
    else:
        functions.reply_LINE(event, TextSendMessage(text="ふぅーーー\nよかったぁーーー"))

#ユーザーからテキストメッセージが送られてきたときの処理
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    functions.show_loading_animation(event) #ローディングアニメーションを表示

    question = event.message.text #ユーザからのメッセージを取得
    if question == '記憶を消す':
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=PostbackAction(label="はい", data="delete")),
            QuickReplyButton(action=PostbackAction(label="いいえ", data="not_delete"))
            ])
        confirm_message = TextSendMessage(text="本当に僕の記憶を消すの…？", quick_reply=quick_reply)
        functions.reply_LINE(event, confirm_message)
    else:
        # ユーザーからのメッセージに対して応答
        text, conversation = functions.generate_response(question, event)
        texts = text.split('\n')     #応答メッセージに改行を含む場合、別の吹き出しとして送信するため分割
        texts = [s for s in texts if s != ''] #空要素があると返信してくれないので削除
        if len(texts) >= 5:     #複数メッセージの送信数に上限があるため、上限を超える際は一つのメッセージとして送信する
            messages = [TextSendMessage(text=text)]
        else:
            messages = [TextSendMessage(text=texts[i]) for i in range(len(texts))]  #複数メッセージ送信の際はTextSendMessageのリストを渡す
        functions.choice_sticker(text, messages)
        
        tmp_path, key_path = functions.make_path(event)
        conversation.append({"user": question, "assistant": text})
        functions.record_to_s3(tmp_path, key_path, conversation)

        functions.reply_LINE(event, messages)

#ユーザーからスタンプが送られてきたときの処理、ランダムでスタンプを送信
@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    package_id, sticker_id = functions.random_sticker()

    functions.reply_LINE(event, StickerSendMessage(package_id=package_id, sticker_id=sticker_id)) 
    #StickerSendMessage(package_id=event.message.package_id,sticker_id=event.message.sticker_id)   オウム返し  

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

    functions.reply_LINE(event, TextSendMessage(text=functions.transcribe_audio(audio_filepath)))  
    functions.delete_tmp_all()

#ユーザから位置情報メッセージが送られたときの処理
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    text, icon_url = functions.weather_info(event)
    functions.reply_LINE(event, [TextSendMessage(text=text), ImageSendMessage(original_content_url=icon_url, preview_image_url=icon_url)])

# メイン関数
if __name__ == '__main__':   #python lineapp.pyとして実行された場合のみ実行が行われる
    # Flaskアプリケーションを起動
    app.run(debug=True)