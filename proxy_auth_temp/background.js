
        var config = {
            mode: "fixed_servers",
            rules: {
                singleProxy: {
                    scheme: "http",
                    host: "185.232.18.41",
                    port: parseInt(63519)
                },
                bypassList: ["localhost"]
            }
        };
        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
        chrome.webRequest.onAuthRequired.addListener(
            function(details) {
                return {authCredentials: {username: "cy3jmdzR", password: "FG4Av12z"}};
            },
            {urls: ["<all_urls>"]},
            ['blocking']
        );
        