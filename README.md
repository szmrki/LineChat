## 概要
- LINEのプラットフォームとOpenAIのAPIを用いたチャットアプリ
- Flaskやマッシュアップの勉強用

## 使用技術
- 言語: Python
- フレームワーク: Flask
- API: OpenAI API, DeepL API, OpenWeatherMap API
- プラットフォーム: LINE Messaging API
- インフラ: AWS (S3, Lambda, DynamoDB)
- デプロイ: Zappa(FlaskアプリをAWS Lambdaにデプロイするツール)

## 機能
- OpenAIのAPIでは自身のLINEのトーク履歴を用いFine Tuningを行ったため、ある程度自然な応答ができる
- 3トーク分の履歴を保持し回答を生成するため文脈に応じたトークが可能
- 以前のトークから24時間以上経過していれば履歴は反映されず, 記憶は消える
- 会話履歴はS3でのファイル保存で対応、ユーザIDのみDBに登録
- 日本語の文字起こし, 外国語音声の翻訳, 天気予報
- サーバーレス環境（AWS Lambda + Zappa）で動作
- ある一定の時間に質問やトークが来るように設定

## インストール & セットアップ
### 環境
- python 3.x
- AWSアカウント
- LINE Developersアカウント
- OpenAI APIキー
- DeepL APIキー
- OpenWeatherMap APIキー

### リポジトリのクローン
~~~sh
git clone https://github.com/szmrki/LineChat.git
cd LineChat
~~~

### 仮想環境の作成
~~~sh
python -m venv venv
. venv/bin/activate #仮想環境の有効化
(venv) pip install -r requirements.txt  #依存関係のインストール
(venv) deactivate #仮想環境の無効化
~~~

### 環境変数の設定
- .envファイルに作成
~~~.env
LINE_BOT_API=your_line_api_key
LINE_WEBHOOK_HANDLER=your_webhook_handler
OPENAI_API_KEY=your_openai_api_key
CONTENT="A description of your bot's background"
DEEPL_API_KEY=your_deepl_api_key
WEATHER_API_KEY=your_openweathermap_api_key
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=your_aws_default_region
FOR_BIRTHDAY="Questions to ask for birthday messages"
~~~

### AWS Lambdaへのデプロイ
- zappaを使用してデプロイを行う
~~~sh
zappa init
zappa deploy
~~~
- 更新する場合
~~~sh
zappa update
zappa schedule #スケジューリングのみ更新する場合
~~~
- ログを見る場合
~~~sh
zappa tail
~~~
- 削除する場合
~~~sh
zappa undeploy
~~~

### LINE BotのWebhook設定
- LINE Developersにログイン
- Messaging API設定→Webhook設定
- Webhook URLにデプロイ時に付与されたURLを記入, 検証で通信できているか確認
- Webhookの利用をオン

