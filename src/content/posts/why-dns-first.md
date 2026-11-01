---
title: "先配好 DNS，再去申请域名"
date: "2026-10-28"
no: "001"
tags: ["cloudflare", "dns", "排错"]
excerpt: "eu.org 在提交申请的那一刻就会去查你填的 NS 是否真的持有这个 zone。顺序反了，会反复撞上一句看起来像权限错误的提示。"
---

申请 `huruiheng.eu.org` 的时候，卡在一个提示上：`Answer not authoritative`。

字面意思是「应答不权威」。第一反应是权限问题——是不是账号没激活、是不是 NS 填错了、是不是 eu.org 收紧了对免费子域的限制。查了一圈，都不是。真正的原因朴素得多：**顺序反了**。

## 那句话到底在说什么

DNS 里有个概念叫权威应答（authoritative answer）。一个域名服务器收到查询时，只有两种情况会回权威应答：它自己就是那个 zone 的主，或者它能从上游拿到权威数据。否则它只能回一个「我不知道」，或者转去问别人——这时候返回的报文里，`AA` 标志位是 0。

eu.org 的申请表单在提交时会做一次真实查询：拿你填的 NS 地址，直接问它 `SOA huruiheng.eu.org` 和 `NS huruiheng.eu.org`，然后检查回包里的 `AA` 位。如果是 0，就记一条错误。

我填的第一版 NS 是 `ns1.huruiheng.eu.org` —— 一个当时根本不存在的名字。第二版换成了 `ns1.google.com`，真实存在、全球可用，但照样报错。原因很简单：Google 的 NS 服务的是 `google.com`，它不知道 `huruiheng.eu.org` 是谁家的，怎么可能给权威应答。

换句话说，**eu.org 要求的不是「一个能用的 NS」，而是「一个已经在托管你这个 zone 的 NS」**。这两个条件差得很远。

## 顺序问题

官方文档里其实写了：先配置 nameserver，再提交申请。但这句话容易被读成「先想好要用哪家 DNS」，而不是「先让那家 DNS 真正接管这个 zone」。

对已经买了域名的人来说，这个区别不存在——你注册商后台填 NS，DNS 商那边加 zone，本来就是这个顺序。但 `eu.org` 是免费二级域，情况倒过来了：你没有控制台可以填 NS，你得先说服 DNS 商「这个域名归我管」，然后才能把 DNS 商给的名字填进申请单。

而 DNS 商通常要求你先证明域名归你。鸡生蛋。

## Cloudflare 这里有个例外

Cloudflare 的规则是「zone 必须是公共后缀（Public Suffix List）的直接下一级」。`eu.org` 在 PSL 里，所以 `huruiheng.eu.org` 可以被当作一个独立 zone 添加，不需要先证明什么。

关键的一点：**zone 添加之后、还没激活的时候，Cloudflare 分配的那两个 NS 就已经在权威应答了**。状态显示 pending，是因为它在等父区把委派指过来；但它自己内部已经认了这个 zone，查询进来会正常回 `AA=1`。

所以整个链路是通的，只是要按这个顺序：

1. Cloudflare 添加 `huruiheng.eu.org`，拿到两个 NS
2. 验证这两个 NS 真的在权威应答
3. 把 NS 填进 eu.org 的申请单
4. 等 eu.org 审核，批了之后父区委派过来，Cloudflare 自动转 Active

第 2 步是我上次忽略的。写了个几十行的小脚本来做：向 8.8.8.8 查 NS 的 A 记录拿到 IP，直接向那个 IP 发 DNS 查询，看 `AA` 位和应答内容。

```
# 简化版核心逻辑
hdr, err = probe(ip, "huruiheng.eu.org", qtype=6)  # SOA
ok = hdr["aa"] == 1 and hdr["rcode"] == 0
```

正向对照用 `ns1.google.com` 查 `google.com`，负向对照用 Cloudflare 的 NS 查一个没加进账号的域名——后者会回 `REFUSED`，eu.org 把它翻译成那句 `Answer not authoritative`。

## 提交时它查了 12 个地址

真正提交的时候，eu.org 打出来的日志比想象中细：

```
---- Checking SOA records for HURUIHENG.EU.ORG
  LENNON.NS.CLOUDFLARE.COM  serial 2418916300  ok   (× 6 个 IP，含 IPv6)
  NAYA.NS.CLOUDFLARE.COM    serial 2418916300  ok   (× 6 个 IP，含 IPv6)
---- Checking NS records
  12/12 ok
```

每个 NS 名字解析出的所有 A 和 AAAA 记录都会逐个查一遍，全部要过。所以「一个 NS 通了」不等于「全部通了」——anycast 的不同节点如果配置不一致，这里就会露馅。Cloudflare 是全节点同步的，12 个全绿。

表单里还有个 `level` 选项，默认是最严的一档：同时校验 SOA 和 NS。另外两档只校验其中一个。没必要降级，能被最严那档通过说明配置本来就是对的。

## 顺带记两个坑

**面板的域名列表是空的，不代表申请失败。** 提交成功后请求进的是审核队列，不显示在 Domains 列表里。我因为这个误判，连续提交了四次，后三次服务端都回 `IGNORED: you already have a pending request`——重复提交不会覆盖，只是被忽略，但对账号没好处。

**联系人信息会进 Whois。** 注册时如果没勾 `Private`，姓名、地址、电话都是公开的。而且这些信息在申请提交后还能改，改完对已经排队的申请同样生效，不用重新提交——因为申请单引用的是 handle，不是快照。

## 所以这件事的通用版本是

任何「先提交、后配置」的系统，都值得反过来想一遍：它在你点提交的那一刻，到底校验了什么。

`Answer not authoritative` 看起来像权限错误，实际是个前置条件检查。把它当成权限问题去查账号状态，方向就偏了。
