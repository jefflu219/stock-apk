[app]
title = 股票基金管理
package.name = stockmanager
package.domain = org.example
source.dir = .
source.include_exts = py,kv
version = 1.0
requirements = python3,kivy==2.2.1,sqlite3
orientation = portrait
fullscreen = 1
log_level = 2

[buildozer]
android.accept_sdk_license = True
android.allow_downloads = True

[android]
android.api = 33
android.minapi = 21
android.sdk = 24
android.ndk = 19c
android.sdk_path = /home/runner/android-sdk
