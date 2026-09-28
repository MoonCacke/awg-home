import base64
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


source = Path(__file__).resolve().parents[1] / "src" / "awg_home_helper.py"
spec = importlib.util.spec_from_file_location("awg_home_helper", source)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def example_profile():
    private = base64.b64encode(bytes(range(32))).decode()
    public = base64.b64encode(bytes(reversed(range(32)))).decode()
    return """[Interface]
PrivateKey = {private}
Address = 10.78.0.9/32
MTU = 1280
DNS = 1.1.1.1, 8.8.8.8
Jc = 4
Jmin = 40
Jmax = 80
S1 = 10
H1 = 12345

[Peer]
PublicKey = {public}
Endpoint = 198.51.100.10:443
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
""".format(private=private, public=public)


class HelperTests(unittest.TestCase):
    def test_profile_is_stripped_without_leaking_dns_to_awg(self):
        parsed = helper.parse_profile(example_profile())
        rendered = helper.stripped_config(parsed)
        self.assertIn("Jc = 4", rendered)
        self.assertIn("AllowedIPs = 0.0.0.0/0", rendered)
        self.assertNotIn("Address =", rendered)
        self.assertNotIn("DNS =", rendered)
        self.assertNotIn("MTU =", rendered)
        self.assertEqual(parsed["dns"], ["1.1.1.1", "8.8.8.8"])

    def test_rejects_unsafe_or_unsupported_profiles(self):
        bad = (
            example_profile().replace("Jmin = 40", "Jmin = 100"),
            example_profile().replace("AllowedIPs = 0.0.0.0/0", "AllowedIPs = 10.0.0.0/8"),
            example_profile().replace("Address = 10.78.0.9/32", "Address = 10.78.0.9/24"),
            example_profile().replace("DNS = 1.1.1.1, 8.8.8.8", "DNS = example.com"),
            example_profile().replace("Jc = 4", "PostUp = touch /tmp/bad"),
        )
        for text in bad:
            with self.subTest(text=text.splitlines()[-3]):
                with self.assertRaises(helper.AWGError):
                    helper.parse_profile(text)

    def test_refuses_existing_tunnel_route(self):
        with patch.object(helper, "run", side_effect=[
            "interface: en0", "interface: utun4"
        ]):
            with self.assertRaisesRegex(helper.AWGError, "другой VPN"):
                helper.refuse_other_vpn("198.51.100.10")

    def test_selects_physical_network_service(self):
        listing = """An asterisk (*) denotes a disabled network service.
(1) Wi-Fi
(Hardware Port: Wi-Fi, Device: en0)
(2) USB LAN
(Hardware Port: USB LAN, Device: en7)
"""
        with patch.object(helper, "run", return_value=listing):
            self.assertEqual(helper.network_service("en0"), "Wi-Fi")
            self.assertEqual(helper.network_service("en7"), "USB LAN")


if __name__ == "__main__":
    unittest.main()
