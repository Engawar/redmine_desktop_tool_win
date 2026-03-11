# Redmine Ticket Tool for Windows

Redmine API を使って、プロジェクト単位でチケット一覧を CSV エクスポートし、編集後に CSV から更新インポートする Windows 向けデスクトップアプリです。

## できること

- `config.json` に Redmine URL / APIキー を保存
- 接続確認
- プロジェクト一覧取得
- 対象PJのチケット一覧を CSV エクスポート
- 更新用CSVを読み込み、Redmineチケットを更新
- インポート失敗行は別CSVに出力

## 更新対応項目

CSV で更新できる主な列:

- `id` 必須
- `subject`
- `status_id`
- `assigned_to_id`
- `priority_id`
- `start_date`
- `due_date`
- `done_ratio`
- `estimated_hours`
- `notes_append` コメント追記
- `description_append` 説明文末尾へ追記

`description_append` を使う場合は、同じ行の `description` 列にエクスポート時点の説明が入っている前提で末尾追記します。

## 配布向け構成

- `app.py` アプリ本体
- `config.json` 設定ファイル
- `build_exe.bat` Windows向けビルドスクリプト
- `build_exe.ps1` PowerShell向けビルドスクリプト
- `RedmineTicketTool.spec` PyInstaller spec
- `assets/app.ico` 任意のアプリアイコン配置場所

## 事前準備

Windows に Python 3.11 以降を入れて、`py` コマンドが使える状態にしてください。

## ローカル実行

```powershell
pip install -r requirements.txt
python app.py
```

## EXE ビルド方法

### バッチでビルド

```bat
build_exe.bat
```

### PowerShellでビルド

```powershell
.\build_exe.ps1
```

ビルド後の成果物:

- `dist\RedmineTicketTool\RedmineTicketTool.exe`
- `dist\RedmineTicketTool\config.json`
- `dist\RedmineTicketTool\README.md`
- `dist\RedmineTicketTool\exports\`

この `RedmineTicketTool` フォルダごと配布してください。

## 初回設定

`config.json` を編集します。

```json
{
  "redmine_url": "https://your-redmine.example.com",
  "api_key": "PUT_YOUR_API_KEY_HERE",
  "default_project_identifier": "sample-project",
  "default_export_dir": "exports",
  "verify_ssl": true,
  "timeout_seconds": 30,
  "page_size": 100
}
```

## 運用イメージ

1. `config.json` に URL と APIキーを設定
2. アプリ起動
3. 接続確認
4. PJ一覧取得
5. 対象PJを選択して CSV エクスポート
6. CSV を編集
7. CSV インポート
8. エラーがあれば `import_errors_*.csv` を確認

## 注意事項

- APIキーに更新権限が必要です
- `status_id` や `assigned_to_id` は Redmine 側のID指定です
- 大量更新前に、必ず検証環境か小規模PJでテストしてください
- 自己署名証明書を使う環境では `verify_ssl` を `false` にできます

## 将来的に追加しやすい機能

- トラッカー / ステータス / 担当者による絞り込み
- 差分プレビュー
- 一括新規起票
- 複数PJ横断エクスポート
- 担当者一覧 / ステータス一覧 / 優先度一覧のマスタ取得
- ログファイル永続化
