import json
import re
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Plain
from astrbot.api.star import Context, Star, StarTools


DEFAULT_CONFIG = {
    "enabled": True,
    "group_whitelist": [],
    "user_whitelist": [],
    "ignore_admin": True,
    "detect_links": True,
    "detect_keywords": True,
    "custom_keywords": [],
    "allowed_domains": [],
    "warning_limit": 3,
    "warning_reset_seconds": 86400,
    "recall_message": True,
    "mute_enabled": False,
    "mute_seconds": 600,
    "warning_template": "⚠️ 请勿发送广告/外链。\n用户：{user}\n原因：{reason}\n警告次数：{count}/{limit}",
    "mute_template": "🚫 {user} 已达到 {limit} 次警告，已尝试禁言 {mute_seconds} 秒。",
}

DEFAULT_KEYWORDS = [
    "加群", "拉群", "群号", "QQ群", "qq 群", "进群", "入群",
    "私聊", "私信", "加我", "联系我", "加好友",
    "微信", "VX", "V信", "薇信", "wx", "wechat",
    "兼职", "刷单", "返利", "推广", "代理", "招商", "引流",
    "代充", "低价", "优惠", "福利", "薅羊毛", "赚钱", "日结",
    "下单", "购买", "出售", "售卖", "包邮", "秒杀",
]

LINK_RE = re.compile(
    r"(?i)(https?://|www\.|[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62})+"
    r"(?:/[^\s\u4e00-\u9fff]*)?)"
)

DOMAIN_RE = re.compile(r"(?i)(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62})+)")


class AntiAdPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.plugin_dir = Path(__file__).parent
        self.config_path = self.plugin_dir / "config.json"
        self.data_dir = Path(StarTools.get_data_dir("astrbot_anti_ad"))
        self.data_dir.mkdir(exist_ok=True)
        self.warn_path = self.data_dir / "warnings.json"

        file_config = self._load_json(self.config_path, DEFAULT_CONFIG)
        self.config = self._merge_config(file_config, config or {})
        self.warnings = self._load_json(self.warn_path, {})

    def _load_json(self, path: Path, default):
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[astrbot_anti_ad] 读取文件失败: {path} - {e}")
        return dict(default) if isinstance(default, dict) else default

    def _save_warnings(self):
        try:
            with self.warn_path.open("w", encoding="utf-8") as f:
                json.dump(self.warnings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[astrbot_anti_ad] 保存警告数据失败: {e}")

    def _merge_config(self, file_config: dict, runtime_config: dict) -> dict:
        result = dict(DEFAULT_CONFIG)
        result.update(file_config or {})
        result.update(runtime_config or {})

        for key in ["group_whitelist", "user_whitelist", "custom_keywords", "allowed_domains"]:
            result[key] = [str(item).strip() for item in (result.get(key, []) or []) if str(item).strip()]

        result["enabled"] = bool(result.get("enabled", True))
        result["ignore_admin"] = bool(result.get("ignore_admin", True))
        result["detect_links"] = bool(result.get("detect_links", True))
        result["detect_keywords"] = bool(result.get("detect_keywords", True))
        result["recall_message"] = bool(result.get("recall_message", True))
        result["mute_enabled"] = bool(result.get("mute_enabled", False))
        result["warning_limit"] = max(1, self._safe_int(result.get("warning_limit"), 3))
        result["warning_reset_seconds"] = max(60, self._safe_int(result.get("warning_reset_seconds"), 86400))
        result["mute_seconds"] = max(60, self._safe_int(result.get("mute_seconds"), 600))
        return result

    def _safe_int(self, value, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _get_group_id(self, event: AstrMessageEvent) -> str:
        try:
            if hasattr(event, "get_group_id") and callable(event.get_group_id):
                value = event.get_group_id()
                if value:
                    return str(value).strip()
        except Exception:
            pass
        for value in [
            getattr(event, "group_id", None),
            getattr(event.message_obj, "group_id", None),
            getattr(event.message_obj, "group", None),
        ]:
            if value:
                return str(value).strip()
        return ""

    def _get_user_id(self, event: AstrMessageEvent) -> str:
        try:
            return str(event.get_sender_id()).strip()
        except Exception:
            sender = getattr(event.message_obj, "sender", None)
            return str(getattr(sender, "user_id", "unknown")).strip()

    def _get_display_name(self, event: AstrMessageEvent) -> str:
        sender = getattr(event.message_obj, "sender", None)
        for value in [
            getattr(sender, "card", None),
            getattr(sender, "nickname", None),
            getattr(sender, "remark", None),
            getattr(event.message_obj, "sender_card", None),
            getattr(event.message_obj, "sender_nickname", None),
        ]:
            text = str(value or "").strip()
            if text:
                return text
        return self._get_user_id(event)

    def _is_group_enabled(self, group_id: str) -> bool:
        whitelist = self.config.get("group_whitelist", []) or []
        return not whitelist or str(group_id) in {str(item) for item in whitelist}

    def _is_admin_or_owner(self, event: AstrMessageEvent) -> bool:
        sender = getattr(event.message_obj, "sender", None)
        for role in [
            getattr(sender, "role", None),
            getattr(event.message_obj, "sender_role", None),
            getattr(event, "sender_role", None),
            getattr(event, "role", None),
        ]:
            if str(role or "").lower() in {"admin", "owner"}:
                return True
        return any(flag is True for flag in [
            getattr(sender, "is_admin", None),
            getattr(sender, "is_owner", None),
            getattr(event.message_obj, "is_admin", None),
            getattr(event.message_obj, "is_owner", None),
        ])

    def _normalize_domain(self, domain: str) -> str:
        return str(domain or "").lower().strip().lstrip(".")

    def _is_allowed_domain(self, domain: str) -> bool:
        domain = self._normalize_domain(domain)
        allowed = [self._normalize_domain(item) for item in self.config.get("allowed_domains", []) or []]
        return any(domain == item or domain.endswith("." + item) for item in allowed)

    def _detect_violation(self, message: str) -> str:
        if self.config.get("detect_links", True):
            for match in LINK_RE.finditer(message):
                text = match.group(0)
                domain_match = DOMAIN_RE.search(text)
                if domain_match and self._is_allowed_domain(domain_match.group(1)):
                    continue
                return "发送外链"

        if self.config.get("detect_keywords", True):
            lower_msg = message.lower().replace(" ", "")
            keywords = DEFAULT_KEYWORDS + (self.config.get("custom_keywords", []) or [])
            for keyword in keywords:
                word = str(keyword or "").strip()
                if word and word.lower().replace(" ", "") in lower_msg:
                    return f"疑似广告关键词：{word}"
        return ""

    def _warning_key(self, group_id: str, user_id: str) -> str:
        return f"{group_id}:{user_id}"

    def _add_warning(self, group_id: str, user_id: str) -> int:
        now = int(time.time())
        key = self._warning_key(group_id, user_id)
        item = self.warnings.get(key, {})
        last_time = self._safe_int(item.get("last_time"), 0)
        count = self._safe_int(item.get("count"), 0)
        if now - last_time > self.config.get("warning_reset_seconds", 86400):
            count = 0
        count += 1
        self.warnings[key] = {"count": count, "last_time": now, "group_id": group_id, "user_id": user_id}
        self._save_warnings()
        return count

    def _get_message_id(self, event: AstrMessageEvent):
        for value in [
            getattr(event.message_obj, "message_id", None),
            getattr(event.message_obj, "id", None),
            getattr(event, "message_id", None),
        ]:
            if value is not None and str(value).strip():
                return value
        return None

    def _get_bot_adapters(self, event: AstrMessageEvent):
        adapters = []
        for src, obj in [
            ("event.bot", getattr(event, "bot", None)),
            ("event.client", getattr(event, "client", None)),
            ("event.adapter", getattr(event, "adapter", None)),
            ("event.platform_adapter", getattr(event, "platform_adapter", None)),
        ]:
            if obj is not None:
                adapters.append((src, obj))
        return adapters

    async def _call_action(self, event: AstrMessageEvent, action: str, **kwargs) -> bool:
        for src, bot in self._get_bot_adapters(event):
            method = getattr(bot, action, None)
            if callable(method):
                try:
                    result = method(**kwargs)
                    if hasattr(result, "__await__"):
                        await result
                    logger.info(f"[astrbot_anti_ad] {src}.{action} 成功")
                    return True
                except Exception as e:
                    logger.info(f"[astrbot_anti_ad] {src}.{action} 失败: {e}")

            call_action = getattr(bot, "call_action", None)
            if callable(call_action):
                try:
                    result = call_action(action, **kwargs)
                    if hasattr(result, "__await__"):
                        await result
                    logger.info(f"[astrbot_anti_ad] {src}.call_action({action}) 成功")
                    return True
                except Exception as e:
                    logger.info(f"[astrbot_anti_ad] {src}.call_action({action}) 失败: {e}")
        return False

    async def _recall_message(self, event: AstrMessageEvent) -> bool:
        message_id = self._get_message_id(event)
        if message_id is None:
            logger.info("[astrbot_anti_ad] 未获取到 message_id，无法撤回")
            return False
        try:
            message_id = int(message_id)
        except Exception:
            pass
        return await self._call_action(event, "delete_msg", message_id=message_id)

    async def _mute_user(self, event: AstrMessageEvent, group_id: str, user_id: str) -> bool:
        try:
            gid = int(group_id)
            uid = int(user_id)
        except Exception:
            gid = group_id
            uid = user_id
        return await self._call_action(
            event,
            "set_group_ban",
            group_id=gid,
            user_id=uid,
            duration=self.config.get("mute_seconds", 600),
        )

    def _at_text_result(self, event: AstrMessageEvent, user_id: str, text: str):
        return event.chain_result([At(qq=str(user_id)), Plain(" " + text)])

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        try:
            if not self.config.get("enabled", True):
                return

            message_str = (event.message_str or "").strip()
            if not message_str:
                return

            group_id = self._get_group_id(event)
            user_id = self._get_user_id(event)
            if not group_id or not self._is_group_enabled(group_id):
                return
            if user_id in {str(item) for item in self.config.get("user_whitelist", []) or []}:
                return
            if self.config.get("ignore_admin", True) and self._is_admin_or_owner(event):
                return

            reason = self._detect_violation(message_str)
            if not reason:
                return

            if self.config.get("recall_message", True):
                await self._recall_message(event)

            count = self._add_warning(group_id, user_id)
            limit = self.config.get("warning_limit", 3)
            display_name = self._get_display_name(event)

            warning_text = self.config.get("warning_template", DEFAULT_CONFIG["warning_template"]).format(
                user=display_name,
                user_id=user_id,
                group_id=group_id,
                reason=reason,
                count=count,
                limit=limit,
            )
            yield self._at_text_result(event, user_id, warning_text)

            if count >= limit and self.config.get("mute_enabled", False):
                muted = await self._mute_user(event, group_id, user_id)
                if muted:
                    mute_text = self.config.get("mute_template", DEFAULT_CONFIG["mute_template"]).format(
                        user=display_name,
                        user_id=user_id,
                        group_id=group_id,
                        limit=limit,
                        mute_seconds=self.config.get("mute_seconds", 600),
                    )
                    yield self._at_text_result(event, user_id, mute_text)
        except Exception as e:
            logger.error(f"[astrbot_anti_ad] 处理群消息失败: {e}")
