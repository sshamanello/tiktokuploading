import zipfile, os, json
from dotenv import load_dotenv

def create_proxy_extension_from_env():
    load_dotenv()
    proxy_type = os.getenv("PROXY_TYPE", "socks5")
    proxy_host = os.getenv("PROXY", "")
    proxy_user = os.getenv("PROXY_USER", "")
    proxy_pass = os.getenv("PROXY_PASS", "")

    if not proxy_host or not proxy_user or not proxy_pass: return None
    if ":" not in proxy_host: return None
    host, port = proxy_host.split(":")

    manifest_json = {
        "version": "1.0.0", "manifest_version": 2, "name": "Proxy Extension",
        "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
        "background": {"scripts": ["background.js"]},
        "minimum_chrome_version": "76.0.0"
    }

    background_js = f'''
    var config = {{
      mode: "fixed_servers",
      rules: {{ singleProxy: {{ scheme: "{proxy_type}", host: "{host}", port: parseInt({port}) }},
                bypassList: ["localhost"] }}
    }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function(){{}});
    chrome.webRequest.onAuthRequired.addListener(
      function(details) {{
        return {{authCredentials: {{username: "{proxy_user}", password: "{proxy_pass}"}}}};
      }},
      {{urls: ["<all_urls>"]}},
      ['blocking']
    );
    '''

    ext_path = os.path.join(os.getcwd(), "proxy_auth_extension.zip")
    with zipfile.ZipFile(ext_path, "w") as zp:
        zp.writestr("manifest.json", json.dumps(manifest_json))
        zp.writestr("background.js", background_js)

create_proxy_extension_from_env()
