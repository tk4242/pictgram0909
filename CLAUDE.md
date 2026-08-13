# CLAUDE.md

**このリポジトリのルールは [`AGENTS.md`](./AGENTS.md) に集約されています。作業前に必ず読んでください。**

`AGENTS.md` は Codex と Claude Code の共通指示書です。ルールを変更するときは
このファイルではなく `AGENTS.md` を編集してください（二重管理を避けるため）。

## Claude Code 固有の補足

- ブランチ名の接頭辞は `claude/` を使います（Codex は `codex/`）。
  どちらの AI が作業したか追えるようにするためのルールです。
- 作業開始時は必ず `git fetch origin` を実行してください。
  Codex が先に push している可能性があります（`AGENTS.md` §5）。
- コミットには Claude Code 既定の trailer をそのまま付けてください。
- VPS（`root@160.251.137.210`）の作業ルールは `AGENTS.md` §6 です。
  **クラウド実行のセッション（Claude Code on the web）には `ssh` クライアントも
  秘密鍵も存在しないため、VPS 作業はローカル実行の Claude Code で行ってください。**

## この環境での注意

`Gemfile` が Ruby 2.4.1 を要求するため、新しい Ruby が入った環境では `bundle install`
が失敗し、**テストを実行できません。** その場合は静的検証にとどめ、
「テスト未実行」であることを必ず報告に明記してください（`AGENTS.md` §2）。
