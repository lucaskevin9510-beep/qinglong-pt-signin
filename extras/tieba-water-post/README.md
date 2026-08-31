# 百度贴吧 APP 自动回帖脚本（青龙）

这是一个适用于青龙面板的贴吧 APP 协议自动回帖脚本。

当前默认配置已经针对 **PT 吧公开水楼** 完成实际验证：

- 吧名：`pt`
- `fid=352902`
- `tid=9739080249`
- 默认回复内容：`绑定`
- 每次任务连续回复：`4` 条
- 每条间隔：`1` 秒
- 贴吧 APP 版本：`22.9.1.0`
- APP 登录接口：`https://tiebac.baidu.com/c/s/login`
- APP 回帖接口：`https://tiebac.baidu.com/c/c/post/add`

> 2026-09-01 已使用贴吧 iOS APP 协议真实运行验证，连续 4 条回帖均成功返回 `post_id`。

---

## 功能

- 使用贴吧 APP 协议登录校验
- 自动从 APP 登录响应中的 `anti.tbs` 获取 TBS
- 自动生成贴吧 APP `sign`
- 支持连续发布多条回复
- 默认连续 4 条，每条间隔 1 秒
- 支持自定义贴吧、帖子、回复内容和次数
- 遇到验证码、验证或风控提示时停止继续发送
- 日志会显示每条回复是否成功以及对应 `post_id`
- 不在脚本中保存真实账号凭据

---

## 已内置的公共 APP 信息

普通用户不需要重新抓这些：

```text
APP_VERSION=22.9.1.0
_client_type=1
_os_version=18.7
from=appstore
subapp_type=tieba
net_type=1
登录接口=https://tiebac.baidu.com/c/s/login
回帖接口=https://tiebac.baidu.com/c/c/post/add
```

脚本中也已经内置当前可用的 APP User-Agent 和签名算法。

### APP sign 算法

当前已验证的签名逻辑：

1. 排除 `sign` 自身
2. 所有参数按 key 升序排序
3. 拼接为连续的 `key=value`
4. 末尾追加：

```text
tiebaclient!!!
```

5. 计算 MD5
6. 转为大写

这些都是公共协议参数，不需要每个人重新抓包。

---

## 必填环境变量

普通用户只需要准备自己的 `BDUSS`。

推荐在青龙环境变量中添加：

```text
名称：TIEBA_BDUSS
值：你自己的 BDUSS
```

也可以直接放整串贴吧 Cookie：

```text
名称：TIEBA_COOKIE
值：包含 BDUSS 的完整 Cookie
```

脚本会自动从中提取 `BDUSS`。

> `BDUSS` 属于账号登录凭据，请不要提交到 GitHub、群聊、Issue、截图或公开日志中。

---

## 如何抓取 BDUSS

下面以 iPhone 为例。

### 方法一：抓贴吧 APP 请求

1. 在手机上安装并打开贴吧 APP。
2. 使用你自己的 HTTPS 抓包工具。
3. 确保手机已经正确安装并信任抓包证书。
4. 打开贴吧 APP，进入任意贴吧或帖子。
5. 在抓包记录中搜索：

```text
tiebac.baidu.com
```

6. 找到贴吧 APP 请求后查看 Cookie 或请求参数。
7. 搜索：

```text
BDUSS
```

常见形式：

```text
BDUSS=xxxxxxxxxxxxxxxx
```

只复制 `BDUSS=` 后面的值，填入青龙环境变量 `TIEBA_BDUSS`。

### 方法二：使用完整 Cookie

如果抓包里看到类似：

```text
BAIDUID=...; BDUSS=...; STOKEN=...; 其他字段=...
```

可以整串复制到：

```text
TIEBA_COOKIE
```

脚本会只提取其中的 `BDUSS`。

---

## 可选设备参数

当前实测中，普通用户只提供 `BDUSS` 就可以完成 APP 登录和回帖。

如果未来贴吧接口调整，或者某些账号返回设备参数相关错误，可以再补充：

```text
TIEBA_CLIENT_ID
TIEBA_CUID
TIEBA_IDFV
TIEBA_Z_ID
TIEBA_STOKEN
TIEBA_OS_VERSION
```

这些参数都是可选的，**不要一开始就全部抓取**。

---

## 如何抓取可选设备参数

如果确实遇到兼容性问题，再执行下面步骤。

### 1. 抓 APP 登录请求

在抓包中搜索：

```text
https://tiebac.baidu.com/c/s/login
```

重点查看 POST 参数。

常见字段包括：

```text
_client_id
cuid
idfv
z_id
stoken
_os_version
```

然后对应填写到青龙：

```text
_client_id  -> TIEBA_CLIENT_ID
cuid        -> TIEBA_CUID
idfv        -> TIEBA_IDFV
z_id        -> TIEBA_Z_ID
stoken      -> TIEBA_STOKEN
_os_version -> TIEBA_OS_VERSION
```

### 2. 不要复制 sign

抓包中的 `sign` 不需要保存。

脚本每次都会根据当前请求参数重新计算，所以旧 `sign` 没有长期使用价值。

### 3. 不要公开唯一设备信息

`CUID`、`IDFV`、`z_id`、`STOKEN` 等可能与设备或账号绑定。

如果只是自己使用，可以放在青龙环境变量中；不要提交到公开仓库。

---

## 青龙依赖

Python 依赖：

```text
requests
```

如果没有安装：

青龙面板 → 依赖管理 → Python3 → 添加：

```text
requests
```

---

## 青龙任务命令

如果脚本文件名为：

```text
tieba_water_post.py
```

任务命令：

```bash
python3 tieba_water_post.py
```

如果通过仓库订阅拉取，请按照青龙实际脚本路径填写。

---

## 默认 PT 吧水楼配置

当前脚本开箱即用的默认值：

```text
TIEBA_KW=pt
TIEBA_FID=352902
TIEBA_TID=9739080249
TIEBA_CONTENT=绑定
TIEBA_POST_COUNT=4
TIEBA_POST_INTERVAL_MIN=1
TIEBA_POST_INTERVAL_MAX=1
```

这些环境变量都不是必填。

如果就是用于当前 PT 吧公开水楼，只需要配置：

```text
TIEBA_BDUSS
```

即可。

---

## 修改成自己的帖子

如果要用于其他允许自动回复的贴吧或帖子，可以设置：

```text
TIEBA_KW=贴吧名称
TIEBA_FID=贴吧fid
TIEBA_TID=帖子tid
TIEBA_CONTENT=回复内容
TIEBA_POST_COUNT=4
```

例如：

```text
TIEBA_KW=pt
TIEBA_FID=352902
TIEBA_TID=9739080249
TIEBA_CONTENT=绑定
TIEBA_POST_COUNT=4
```

---

## 如何获取 tid

帖子地址一般类似：

```text
https://tieba.baidu.com/p/9739080249
```

其中：

```text
9739080249
```

就是 `tid`。

---

## 如何获取 fid

### 方法一：抓 APP 请求

进入目标贴吧，在抓包中搜索：

```text
tiebac.baidu.com
```

查看吧页或帖子相关请求参数，通常可以找到：

```text
fid
```

### 方法二：查看 APP 接口响应

打开目标吧或帖子后，在 JSON 返回中搜索：

```text
forum_id
```

或：

```text
fid
```

然后把对应数字填入：

```text
TIEBA_FID
```

---

## 连续回复次数

默认：

```text
TIEBA_POST_COUNT=4
```

即一次运行连续发送 4 条。

如果只想发 1 条：

```text
TIEBA_POST_COUNT=1
```

---

## 回复间隔

默认固定 1 秒：

```text
TIEBA_POST_INTERVAL_MIN=1
TIEBA_POST_INTERVAL_MAX=1
```

例如想随机 2～4 秒：

```text
TIEBA_POST_INTERVAL_MIN=2
TIEBA_POST_INTERVAL_MAX=4
```

---

## DRY RUN 测试模式

如果只想测试登录和参数，不真正发布：

```text
TIEBA_DRY_RUN=1
```

确认日志正常后删除该变量，或者改成：

```text
TIEBA_DRY_RUN=0
```

即可正式发布。

---

## 运行示例

```text
========== 百度贴吧 APP 自动回帖 ==========
📱 APP 模式：Tieba iOS 22.9.1.0
🌐 发布接口：https://tiebac.baidu.com/c/c/post/add
📌 吧名：pt吧
🆔 fid：352902
🧵 tid：9739080249
💬 本次回复：绑定
🔢 本次连续发布：4 条
🔐 BDUSS：xxxx...xxxx
✅ APP 登录校验成功
👤 用户：示例用户
🧩 TBS：xxxx...xxxx
🚀 开始连续发布 4 条“绑定”...

[1/4] 正在发布“绑定”...
✅ 第 1 条发布成功，post_id：123456789001
⏳ 1.0 秒后发布下一条...

[2/4] 正在发布“绑定”...
✅ 第 2 条发布成功，post_id：123456789002
⏳ 1.0 秒后发布下一条...

[3/4] 正在发布“绑定”...
✅ 第 3 条发布成功，post_id：123456789003
⏳ 1.0 秒后发布下一条...

[4/4] 正在发布“绑定”...
✅ 第 4 条发布成功，post_id：123456789004

========== 发布汇总 ==========
✅ 成功：4/4
❌ 失败：0
========== 任务结束 ==========
```

---

## 建议定时

当前默认逻辑是一次执行直接连续完成 4 条，所以每天只需要运行一次。

例如：

```cron
17 8 * * *
```

---

## 安全说明

仓库中可以公开并共同使用的是：

- APP 版本
- `_client_type`
- `_os_version`
- User-Agent 模板
- API 路径
- `sign` 算法
- 当前公开水楼的 `fid / tid / kw / content`

不应该公开的是：

- `BDUSS`
- `STOKEN`
- 个人 Cookie
- 唯一设备 `CUID`
- `IDFV`
- `z_id`
- 其他账号或设备专属 token

这些敏感值统一通过青龙环境变量保存。

---

## 免责声明

本脚本仅用于个人账号自动化、协议学习以及目标贴吧明确允许的自动回复场景。

请遵守百度贴吧规则、目标贴吧吧规及对应帖子的使用规则。不要将脚本用于批量广告、骚扰、刷屏或其他未经允许的自动发布行为。

贴吧 APP 接口和参数可能随版本更新发生变化。如果脚本失效，可以通过新的 APP 抓包重新确认接口和字段。
