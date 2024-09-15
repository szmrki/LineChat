from flask import Flask, request, abort
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os

app = Flask(__name__)  #flaskのインスタンスを作成
CORS(app)

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

#ユーザーからメッセージが送られてきたときの処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    question = event.message.text #ユーザからのメッセージを取得
    # ユーザーからのメッセージに対して応答
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=generate_response(question))
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

