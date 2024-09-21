from flask import Flask, request, abort
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerMessage, StickerSendMessage
import openai
import os
from dotenv import load_dotenv
import random

app = Flask(__name__)  #flaskのインスタンスを作成
CORS(app)

load_dotenv() #pyenv環境内ででAPIキーを取得するため

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
def handle_message(event):
    question = event.message.text #ユーザからのメッセージを取得
    # ユーザーからのメッセージに対して応答
    text = generate_response(question)  #応答メッセージの作成
    texts = text.split('\n')     #応答メッセージに改行を含む場合、別の吹き出しとして送信するため分割
    line_bot_api.reply_message(
        event.reply_token,
        [TextSendMessage(text=texts[i]) for i in range(len(texts))] #複数メッセージ送信の際はTextSendMessageのリストを渡す
    )

#ユーザーからスタンプが送られてきたときの処理 とりあえずランダムでスタンプを送信
@handler.add(MessageEvent, message=StickerMessage)
def handle_message(event):
    package_id_list = [11537, 11538, 11539]
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
        StickerSendMessage(package_id=package_id_list[num], sticker_id=sticker_id)
    )

# 質問に対するレスポンスを生成する関数
def generate_response(question):
    # OpenAI APIキーを設定
    api_key = os.environ["OPENAI_API_KEY"]
    client = openai.OpenAI(api_key=api_key)
    
    # ファンチューニング済みのモデルに質問を送信してレスポンスを取得
    response = client.chat.completions.create(
        model="ft:gpt-4o-mini-2024-07-18:personal::9xbwUFNo",
        messages=[
            {"role":"system", "content":"You are my boy-friend. You love me and I love you."},
            {"role":"user", "content": question}
            ],
    #max_tokens=50
    )
    eng_response = response.choices[0].message.content
    return eng_response

# メイン関数
if __name__ == '__main__':   #python answer.pyとして実行された場合のみ実行が行われる
    # Flaskアプリケーションを起動
    app.run(debug=True)

