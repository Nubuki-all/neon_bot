import asyncio
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codes = load_module("genshin_utils_test", "bot/utils/genshin_utils.py")


class FeedTests(unittest.TestCase):
    def test_formats_filtering_and_case_insensitive_duplicates(self):
        self.assertEqual(
            codes.parse_codes(
                {
                    "game": "genshin",
                    "codes": [
                        {"code": "NEW12345", "status": "OK"},
                        {"code": "new12345", "status": "OK"},
                        {"code": "EXPIRED1", "status": "NOT_OK"},
                        {"code": "WRONG123", "game": "nap"},
                        {"code": "bad code\nhttps://example.com"},
                    ],
                }
            ),
            ["NEW12345"],
        )
        self.assertEqual(
            codes.parse_codes(
                {
                    "active": [{"code": "GENSHINGIFT"}],
                    "inactive": [{"code": "EXPIRED1"}],
                }
            ),
            ["GENSHINGIFT"],
        )
        with self.assertRaises(ValueError):
            codes.parse_codes({"unknown": []})
        with self.assertRaises(ValueError):
            codes.parse_codes({"game": "nap", "codes": []})

    def test_exact_message_and_poll_interval(self):
        self.assertEqual(
            codes.format_code("NEW12345"),
            (
                "[GI] - new code\nNEW12345\n"
                "https://genshin.hoyoverse.com/en/gift?code=NEW12345"
            ),
        )
        with patch.object(codes.random, "randint", return_value=1200) as randint:
            self.assertEqual(codes.next_check_seconds(), 1200)
        randint.assert_called_once_with(900, 3600)

    def test_fallback_after_feed_failure(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"active": [{"code": "NEW12345"}]}'
        )
        with patch.object(
            codes, "urlopen", side_effect=[URLError("down"), response]
        ) as get:
            self.assertEqual(codes.fetch_codes(), ["NEW12345"])
        self.assertEqual(get.call_count, 2)

    def test_empty_feed_is_success_and_does_not_use_stale_fallback(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"codes": []}'
        with patch.object(codes, "urlopen", return_value=response) as get:
            self.assertEqual(codes.fetch_codes(), [])
        get.assert_called_once()


class StoreTests(unittest.TestCase):
    def test_baseline_per_chat_history_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codes.json"
            store = codes.CodeStore(path)
            store.subscribe("first", ["OLD12345"])
            store.subscribe("second", ["OLD12345"])
            store.subscribe("first", ["NEW12345"])
            self.assertEqual(
                store.pending("first", ["old12345", "NEW12345"]), ["NEW12345"]
            )
            store.delivered("first", "NEW12345")
            reloaded = codes.CodeStore(path)
            self.assertEqual(reloaded.pending("first", ["NEW12345"]), [])
            self.assertEqual(reloaded.pending("second", ["NEW12345"]), ["NEW12345"])
            reloaded.unsubscribe("first")
            self.assertNotIn("first", codes.CodeStore(path).chats)

    def test_damaged_history_is_not_erased(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codes.json"
            path.write_text(json.dumps({"chat": "damaged"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                codes.CodeStore(path)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"chat": "damaged"}
            )


class WatcherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.watcher = codes.GenshinWatcher(Path(self.tmp.name) / "codes.json")
        self.send = AsyncMock()

    async def test_no_subscriptions_means_no_network(self):
        with patch.object(codes, "fetch_codes") as fetch:
            await self.watcher.check(self.send, lambda _: True)
        fetch.assert_not_called()

    async def test_only_subscribed_enabled_chats_receive_new_codes(self):
        self.watcher.store.subscribe("allowed", ["OLD12345"])
        self.watcher.store.subscribe("blocked", [])
        with patch.object(codes, "fetch_codes", return_value=["OLD12345", "NEW12345"]):
            await self.watcher.check(self.send, lambda chat: chat == "allowed")
            await self.watcher.check(self.send, lambda chat: chat == "allowed")
        self.send.assert_awaited_once_with("allowed", codes.format_code("NEW12345"))

    async def test_failed_send_is_retried(self):
        self.watcher.store.subscribe("chat", [])
        self.send.side_effect = [RuntimeError("offline"), None]
        with patch.object(codes, "fetch_codes", return_value=["NEW12345"]):
            with self.assertLogs(codes.LOG.name, level="ERROR"):
                await self.watcher.check(self.send, lambda _: True)
            self.assertEqual(
                self.watcher.store.pending("chat", ["NEW12345"]), ["NEW12345"]
            )
            await self.watcher.check(self.send, lambda _: True)
        self.assertEqual(self.send.await_count, 2)

    async def test_disable_before_delivery_stops_posts(self):
        self.watcher.store.subscribe("chat", [])
        allowed = [True, False]
        with patch.object(codes, "fetch_codes", return_value=["NEW12345"]):
            await self.watcher.check(self.send, lambda _: allowed.pop(0))
        self.send.assert_not_awaited()

    async def test_start_is_idempotent_and_stop_cancels_the_worker(self):
        async def wait(*_):
            await asyncio.Event().wait()

        with patch.object(self.watcher, "_run", side_effect=wait) as run:
            self.watcher.start(self.send, lambda _: True)
            task = self.watcher._task
            self.watcher.start(self.send, lambda _: True)
            self.assertIs(self.watcher._task, task)
            await asyncio.sleep(0)
            run.assert_awaited_once()
            await self.watcher.stop()
        self.assertTrue(task.cancelled())
        self.assertIsNone(self.watcher._task)


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = SimpleNamespace(
            get_group_info=AsyncMock(return_value=SimpleNamespace(Participants=[])),
            send_message=AsyncMock(),
        )
        self.runtime = SimpleNamespace(
            client=self.client,
            is_connected=True,
            paused=False,
            offline=False,
        )
        self.permissions = types.ModuleType("bot.utils.msg_utils")
        self.permissions.chat_is_allowed = MagicMock(return_value=True)
        self.permissions.user_is_allowed = MagicMock(return_value=True)
        self.permissions.user_is_privileged = MagicMock(return_value=False)
        self.permissions.user_is_admin = MagicMock(return_value=True)
        config = types.ModuleType("bot.config")
        config.bot = self.runtime
        config.conf = SimpleNamespace(CMD_PREFIX=".")
        jid = types.ModuleType("neonize.utils.jid")
        jid.build_jid = lambda user, server: SimpleNamespace(User=user, Server=server)
        modules = {
            name: types.ModuleType(name)
            for name in (
                "bot",
                "bot.utils",
                "neonize",
                "neonize.utils",
            )
        }
        modules.update(
            {
                "bot.config": config,
                "bot.utils.genshin_utils": codes,
                "bot.utils.msg_utils": self.permissions,
                "neonize.utils.jid": jid,
            }
        )
        with patch.dict(sys.modules, modules):
            self.handler = load_module(
                "genshin_handler_test", "bot/workers/handlers/genshin.py"
            )
        self.handler.watcher = codes.GenshinWatcher(Path(self.tmp.name) / "codes.json")
        self.event = SimpleNamespace(
            from_user=SimpleNamespace(id="member"),
            chat=SimpleNamespace(
                id="group", server="g.us", is_group=True, jid="group-jid"
            ),
            reply=AsyncMock(),
        )

    async def test_subscribe_and_unsubscribe(self):
        with patch.object(self.handler, "fetch_codes", return_value=["OLD12345"]):
            await self.handler.genshin_handler(self.event, "on", self.client)
        self.assertIn("group@g.us", self.handler.watcher.store.chats)
        with patch.object(self.handler, "fetch_codes") as fetch:
            await self.handler.genshin_handler(self.event, "on", self.client)
        fetch.assert_not_called()
        await self.handler.genshin_handler(self.event, "off", self.client)
        self.assertNotIn("group@g.us", self.handler.watcher.store.chats)

    async def test_non_admin_cannot_change_group_subscription(self):
        self.permissions.user_is_admin.return_value = False
        with patch.object(self.handler, "fetch_codes") as fetch:
            await self.handler.genshin_handler(self.event, "on", self.client)
        fetch.assert_not_called()
        self.assertIn("Only group admins", self.event.reply.call_args.args[0])

    async def test_blocked_chat_or_user_cannot_request_codes(self):
        for permission in (
            self.permissions.chat_is_allowed,
            self.permissions.user_is_allowed,
        ):
            permission.return_value = False
            with patch.object(self.handler, "fetch_codes") as fetch:
                await self.handler.genshin_handler(self.event, "codes", self.client)
            fetch.assert_not_called()
            permission.return_value = True

    async def test_current_codes_use_the_requested_format(self):
        with patch.object(self.handler, "fetch_codes", return_value=["NEW12345"]):
            await self.handler.genshin_handler(self.event, "codes", self.client)
        self.event.reply.assert_awaited_once_with(
            codes.format_code("NEW12345"), quote=False, link_preview=False
        )

    async def test_background_posts_respect_pause_and_chat_policy(self):
        self.assertTrue(self.handler._chat_is_allowed("group@g.us"))
        self.runtime.paused = True
        self.assertFalse(self.handler._chat_is_allowed("group@g.us"))
        self.runtime.paused = False
        self.permissions.chat_is_allowed.return_value = False
        self.assertFalse(self.handler._chat_is_allowed("group@g.us"))


if __name__ == "__main__":
    unittest.main()
