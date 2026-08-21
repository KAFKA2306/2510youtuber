# 2510youtuber Agent Operating Contract

`2510youtuber` は2025-10期のYouTube生成実装を再現・診断できる状態で保持するlegacy repositoryです。現在の後継は `KAFKA2306/2511youtuber` です。新機能は、ユーザーがこのrepositoryを明示しない限り後継側へ寄せます。

## Authority

判断順序は次です。

1. 現在のユーザー指示
2. この `AGENTS.md`
3. 現在の実行可能コード・設定・test・CI・runtime evidence
4. 現在の公式upstream/API documentation
5. README / `docs/` / historical Issue・PR
6. 推論

古い文書で現在のコードを上書きしません。未観測状態は `UNVERIFIED` のまま扱います。

## Scope

保守対象は主に次です。

- `app/`: runtime / workflow / models / media services
- `config.yaml` と `app/config/`: repository固有設定・prompt
- `tests/`: regression evidence
- `scripts/`: maintenance / analysis
- `docs/`: 現行実装の利用・保守に必要な説明

既存挙動の修復、security、data/provenance、test、diagnosabilityを優先します。無関係なmodernization、後継repositoryのarchitecture移植、将来用wrapperは追加しません。

## Change policy

- 既存・標準機能を再利用し、`DELETE > MERGE > REPLACE > ADD` を優先する。
- 同じ責務のconfig、helper、workflow、schema、documentation、state storeを増やさない。
- repository固有の略語、maturity level、named gate、confidence score、独自taxonomyを実要件なしに作らない。
- 変更前にopen PR / branch / owning Issueを確認し、canonical worklineを再利用する。
- mutationは1つずつ行い、write後にread-backする。
- mergeはexact PR headと必要なCI結果を確認し、可能ならexpected head SHAを固定する。
- 未実行test、external API、render、upload、publicationをPASSと報告しない。

## Documentation

- `README.md`: repositoryの役割、後継、最短の実行・検証入口
- `AGENTS.md`: agent/repository運用契約
- `docs/JAPANESE_MASTER_GUIDE.md`: legacy実装の詳細な日本語運用ガイド
- その他の `docs/`: 上記と重複しない現在有効なarchitecture/API/data/media説明だけ残す

redirectだけの文書、未参照prototype、現在コードと矛盾する設計資料、同じ手順の重複コピーは削除します。source code、schema、workflow、upstream docsを長文で複製せず、repository固有の差分だけ文書化します。

## Configuration and secrets

- repository defaultsは現在の `config.yaml` / loader pathを使い、競合する設定源を追加しない。
- API key、Cookie、OAuth、YouTube credential、private webhook、service-account secretをcommit・fixture・log・prompt・Issue・PRへ入れない。
- `.env` 等のcredential storeはlocal/runtime concernとしてuntrackedに保つ。
- 外部実行前に現在のloader/validatorで設定を確認する。

## LLM and factual content

LLM outputはuntrusted inputです。

- 現在のPydantic/structured-output pathで検証してから下流へ渡す。
- promptでしか守れない制約を増やす前にdeterministic validator/formatterを使う。
- newsの数値・日付・固有名・因果を補完しない。重要事実は取得元と時刻を保持し、可能ならprimary sourceで確認する。
- generated proseをevidence扱いしない。
- fallback artifactをrequested resultの成功として扱わない。

## Media and publication

renderとpublicationを分けます。YouTube公開を伴う場合は、exact final artifact、必要なQA、metadata/channel、明示的な公開許可を確認し、既存publish pathを使い、remote receipt/stateを取得します。local renderやupload attemptだけで公開成功とはしません。

## Validation

安価なdeterministic checkから実行します。

```bash
uv run python -m compileall -q app tests
uv run pytest tests/unit -v
uv run ruff check .
uv run ruff format --check .
```

必要な場合のみ対象を広げます。

```bash
uv run python -m app.main daily
uv run python test_crewai_flow.py
```

外部API・media生成・uploadを伴う高コスト処理は、taskのacceptanceに必要な場合だけ実行します。CI successはそのexact SHAで実際に走ったcheckだけのevidenceです。

## Completion

完了前に、変更結果、関連test/CI、mainへのread-back、必要なexternal postcondition、task-created residueを確認します。temporary media/log、generated intermediate、secret、stale fixture、不要branch/PRを残しません。

最終報告は、repository/PR、実質的なBefore->After、実行したtest/CI、commit/merge SHA、external receipt、残る `UNVERIFIED` / blockerだけを簡潔に記録します。
