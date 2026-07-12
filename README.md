# astrbot_anti_ad

**AstrBot + NapCat 群聊反广告插件：发链接/广告自动警告**

## 功能

- 检测群聊外链：`http://`、`https://`、`www.`、常见域名格式
- 检测广告关键词：加群、私聊、微信、兼职、返利、代充、推广等
- 支持自定义广告关键词
- 支持允许域名白名单
- 支持群白名单、用户白名单
- 支持忽略群主/管理员
- 支持自动撤回违规消息
- 支持累计警告次数
- 支持达到警告上限后自动禁言

> 自动撤回和禁言需要 NapCat/OneBot 支持，并且机器人账号在群内具备对应权限。禁言默认关闭，避免误伤。

## 安装

把整个 `astrbot_anti_ad` 文件夹放到 AstrBot 的插件目录，例如：

```text
AstrBot/data/plugins/astrbot_anti_ad
```

然后在 AstrBot 后台启用插件，或重启 AstrBot。

## 默认效果

群成员发送链接或疑似广告时，机器人会回复：

```text
⚠️ 请勿发送广告/外链。
用户：某用户
原因：发送外链
警告次数：1/3
```

如果 `recall_message` 开启，并且机器人有权限，会同时尝试撤回原消息。

## 配置说明

| 配置项 | 默认值 | 说明 |
|---|---:|---|
| `enabled` | `true` | 是否启用插件 |
| `group_whitelist` | `[]` | 群白名单，留空表示所有群生效 |
| `user_whitelist` | `[]` | 用户白名单，白名单用户不检测 |
| `ignore_admin` | `true` | 是否忽略群主/管理员 |
| `detect_links` | `true` | 是否检测链接 |
| `detect_keywords` | `true` | 是否检测广告关键词 |
| `custom_keywords` | `[]` | 自定义广告关键词 |
| `allowed_domains` | `[]` | 允许发送的域名 |
| `warning_limit` | `3` | 警告上限 |
| `warning_reset_seconds` | `86400` | 超过多久未违规后重置警告次数 |
| `recall_message` | `true` | 是否自动撤回违规消息 |
| `mute_enabled` | `false` | 达到警告上限后是否禁言 |
| `mute_seconds` | `600` | 禁言时长，单位秒 |
| `warning_template` | 见配置文件 | 警告文案 |
| `mute_template` | 见配置文件 | 禁言文案 |

## 推荐配置示例

只在指定群启用，允许游戏官网链接，达到 3 次警告后禁言 10 分钟：

```json
{
  "enabled": true,
  "group_whitelist": ["123456789"],
  "user_whitelist": [],
  "ignore_admin": true,
  "allowed_domains": ["example.com", "qq.com"],
  "warning_limit": 3,
  "recall_message": true,
  "mute_enabled": true,
  "mute_seconds": 600
}
```

## 注意事项

1. 发 `.com`、`.cn` 这类域名也可能被识别为链接。
2. 如果误拦截游戏官网或公告链接，把域名加入 `allowed_domains`。
3. 如果撤回失败，请检查机器人是否是群管理员，以及 NapCat 是否允许调用 `delete_msg`。
4. 如果禁言失败，请检查机器人是否是群管理员，以及 NapCat 是否允许调用 `set_group_ban`。

## 支持平台

- aiocqhttp / OneBot v11 / NapCat
- qq_official
- qq_official_webhook
- satori
