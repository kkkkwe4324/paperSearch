# Zotero topic-classification example

Read-only snapshot of the user's active Zotero collections on 2026-11-07. This illustrates the **classification style**, not a permanent routing table. Always run `paper-downloader zotero collections` before classifying a new paper and use the returned collection keys and actual parent relationships.

```text
01 端侧大模型系统
  01.1 推理性能与能耗基准
  01.2 热管理与频率调度
  01.3 服务框架与请求调度
03 能源与微电网
  03.3 区块链与点对点能源交易
    03.3.1 点对点能源交易与碳感知
06 卫星计算与网络
  06.1 大模型推理与遥感应用
  06.2 任务卸载与协同调度
  06.3 能源调度与热管理
10投机解码
  05.6 纯边缘投机解码
  05.7 边云协同投机解码
  05.8 VLM投机解码
09 杂项与待归类
```

The `05.6`–`05.8` names really are children of `10投机解码` in the active tree. Do not infer their parent from the numeric prefix, rename them automatically, or create replacement duplicates. A paper about satellite–cloud speculative decoding might belong to `06 卫星计算与网络`, `10投机解码`, and `10投机解码 / 05.7 边云协同投机解码`; add the exact child only after checking its actual method and scenario. An idea/direction in the filesystem does not itself require a Zotero collection.

If an existing child does not fit, use the applicable broad root and record a proposed new child for taxonomy review. If even the broad root is unclear, mark the item pending or use the existing `09 杂项与待归类` staging collection. A single Zotero item may be in several collections; retain its previous memberships.
