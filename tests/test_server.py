import http.client
import json
import threading
import time
import unittest

from helpers import TempHome

from orbitcore import server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.home_ctx = TempHome()
        self.h = self.home_ctx.__enter__()
        config = self.h.workspace.load()
        config["actions"] = {"tidy-files": {"params": self.h.tidy_params()}}
        self.h.workspace.save(config)
        self.app = server.App(self.h.workspace, 0)
        self.httpd = server.OrbitHTTPServer(("127.0.0.1", 0), server.make_handler(self.app))
        self.port = self.httpd.server_address[1]
        self.app.port = self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()
        self.token = self.app.token

    def tearDown(self):
        self.app.stop_event.set()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.home_ctx.__exit__(None, None, None)

    def request(self, method, path, body=None, headers=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        all_headers = {"Host": host or f"127.0.0.1:{self.port}"}
        all_headers.update(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            all_headers.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=all_headers)
        response = conn.getresponse()
        payload = response.read()
        conn.close()
        return response, payload

    def auth(self, extra=None):
        headers = {"X-Orbit-Token": self.token}
        headers.update(extra or {})
        return headers

    def test_ping_and_redirect(self):
        response, payload = self.request("GET", "/api/ping")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(payload)["app"], "orbit-desktop")
        response, _ = self.request("GET", "/")
        self.assertEqual(response.status, 302)
        self.assertRegex(response.getheader("Location"), r"^/themes/[a-z0-9-]+/\?live=1$")

    def test_theme_page_gets_token_and_sdk_is_served(self):
        response, payload = self.request("GET", "/themes/deep-orbit/")
        self.assertEqual(response.status, 200)
        self.assertIn(f'name="orbit-token" content="{self.token}"'.encode(), payload)
        response, payload = self.request("GET", "/sdk/orbit.js")
        self.assertEqual(response.status, 200)
        self.assertIn(b"livelyWallpaperPlaybackChanged", payload)

    def test_api_requires_token(self):
        response, _ = self.request("GET", "/api/state")
        self.assertEqual(response.status, 401)
        response, payload = self.request("GET", "/api/state", headers=self.auth())
        self.assertEqual(response.status, 200)
        state = json.loads(payload)
        ids = {t["id"] for t in state["themes"]}
        self.assertTrue({"ink-study", "deep-orbit", "defrag-95"} <= ids)
        self.assertIn("tidy-files", state["actions"])

    def test_rejects_foreign_hosts_origins_and_preflight(self):
        response, _ = self.request("GET", "/api/ping", host="evil.example:80")
        self.assertEqual(response.status, 403)
        response, _ = self.request("POST", "/api/actions/tidy-files/status", body={}, headers=self.auth({"Origin": "https://evil.example"}))
        self.assertEqual(response.status, 403)
        response, _ = self.request("OPTIONS", "/api/actions/tidy-files/run")
        self.assertEqual(response.status, 403)
        response, _ = self.request("POST", "/api/actions/tidy-files/status", body=None, headers=self.auth({"Content-Type": "text/plain"}))
        self.assertEqual(response.status, 400)

    def test_static_files_cannot_escape_the_theme(self):
        for path in ("/themes/ink-study/../../runtime/orbitcore/config.py", "/themes/ink-study/%2e%2e/%2e%2e/SKILL.md", "/sdk/../SKILL.md"):
            response, _ = self.request("GET", path)
            self.assertEqual(response.status, 404, path)

    def test_run_action_and_activate_theme(self):
        self.h.file("a.pdf")
        response, payload = self.request("POST", "/api/actions/tidy-files/status", body={}, headers=self.auth())
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(payload)["data"]["pending"], 1)
        response, payload = self.request("POST", "/api/actions/nope/run", body={}, headers=self.auth())
        self.assertEqual(response.status, 404)
        response, payload = self.request("POST", "/api/theme/activate", body={"id": "defrag-95"}, headers=self.auth())
        self.assertEqual(response.status, 200)
        self.assertEqual(self.h.workspace.load()["active_theme"], "defrag-95")

    def test_progress_events_reach_open_pages(self):
        for name in ("a.pdf", "b.png", "c.txt"):
            self.h.file(name)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("GET", f"/api/events?token={self.token}", headers={"Host": f"127.0.0.1:{self.port}"})
        stream = conn.getresponse()
        self.assertEqual(stream.status, 200)
        seen = []

        def read_events():
            buffer = b""
            while len([s for s in seen if s.get("phase") in ("done", "error")]) == 0:
                chunk = stream.fp.readline()
                if not chunk:
                    return
                buffer += chunk
                if chunk == b"\n":
                    lines = buffer.decode("utf-8").splitlines()
                    event = next((l[7:] for l in lines if l.startswith("event: ")), "")
                    data = next((l[6:] for l in lines if l.startswith("data: ")), "{}")
                    if event == "action":
                        seen.append(json.loads(data))
                    buffer = b""

        reader = threading.Thread(target=read_events, daemon=True)
        reader.start()
        time.sleep(0.3)
        response, payload = self.request("POST", "/api/actions/tidy-files/run", body={}, headers=self.auth({"X-Orbit-Client": "test"}))
        self.assertEqual(response.status, 200, payload)
        reader.join(timeout=10)
        conn.close()
        phases = [e["phase"] for e in seen]
        self.assertEqual(phases[0], "start")
        self.assertEqual(phases.count("progress"), 3)
        self.assertEqual(phases[-1], "done")
        self.assertTrue(all(e.get("client") == "test" for e in seen))


if __name__ == "__main__":
    unittest.main()
