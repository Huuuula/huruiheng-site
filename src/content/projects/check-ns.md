---
title: "check_ns.py"
date: "2026-10-31"
no: "03"
summary: "几十行 Python，给定域名和一组 NS 名，逐个解析 IP（含 IPv6），直接向该 IP 查 SOA 与 NS，检查回包 AA 位。"
status: "已完成"
stack: ["python", "dns", "cli"]
period: "2026"
link: ""
excerpt: "几十行 Python，给定域名和一组 NS 名，逐个解析 IP（含 IPv6），直接向该 IP 查 SOA 与 NS，检查回包 AA 位。"
---

check_ns.py 只有几十行：给定域名和一组 NS 名，逐个解析出 IP（含 IPv6），再直接向这些 IP 查询 SOA 与 NS 记录，检查回包的 AA 位是否置位。

它要回答的是一个经常被混淆的问题：NS 记录存在，不等于这台 NS 真的托管了这个 zone。只看解析结果，会把「名字能查到」误当成「服务已就绪」。

直连 IP 查询绕开了递归解析器的缓存，AA 位则说明回包是否来自该 zone 的权威服务器。两者合起来，才能判断托管是否真的生效。

一个具体的参照：Cloudflare 的 NS 对未加入账号的 zone 会回 REFUSED。这正好说明「NS 在线」和「NS 对这个 zone 有权威」是两件事。

## 要点

- 支持 IPv4 与 IPv6 的 NS 地址解析
- 直接向 NS 的 IP 查询 SOA 与 NS
- 检查 AA 位判断权威应答
- 用 REFUSED 识别未托管的 zone
