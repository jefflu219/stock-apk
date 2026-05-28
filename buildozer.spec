[app]
title = 股票基金管理
package.name = stockmanager
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,sqlite3
orientation = portrait
fullscreen = 1
log_level = 2
warn_on_root = 1

[buildozer]
android.accept_sdk_license = True
android.allow_downloads = True

[android]
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.sdk = 24
android.ndk = 19c
