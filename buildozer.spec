[app]
# (str) Title of your application
title = Safer Gas

# (str) Package name
package.name = safergas

# (str) Package domain (should be unique)
package.domain = org.imaxeuno

# (str) Source code where your main.py is located
source.dir = .

# (str) The main .py file
source.main = main.py

# (list) Supported orientations
orientation = portrait

# (bool) Fullscreen
fullscreen = 0

# (str) Application versioning
version = 1.0.0

# (list) Permissions
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,BLUETOOTH_ADVERTISE,ACCESS_FINE_LOCATION,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET

# (list) Application requirements
# Core dependencies + Bluetooth, Graph, Pandas
requirements = python3,kivy==2.3.0,kivymd,pyjnius,plyer,pandas,pyserial,kivy_garden.graph,matplotlib

# (str) Custom source folders for garden
garden_requirements = graph

# (str) Application icon (optional)
icon.filename = assets/icon.png

# (str) Presplash screen
presplash.filename = assets/presplash.png

# (str) Supported Android SDKs
android.api = 34
android.minapi = 27
android.ndk = 25b

# (bool) Indicate if app should include a launcher icon
android.include_ext = True

# (list) Features required by app
android.features = android.hardware.bluetooth, android.hardware.location

# (str) Entry point
entrypoint = main.py

# (str) Window mode (optional, affects desktop)
window_mode = single

# (bool) Enable logcat logs
log_level = 2

# (bool) Indicates whether your app should stop logcat
logcat_filter = *:S python:D

# (str) Presplash color (black)
presplash_color = #000000

# (bool) Hide the title bar
android.hide_titlebar = 1

# (str) Adaptive icon background (optional)
adaptive_icon.background = #000000
adaptive_icon.foreground = assets/icon.png

# (list) Patterns to ignore when packaging app
exclude_patterns = tests, __pycache__, .git, .idea, *.bak

# (str) Enable automatic storage of user data dir
android.private_storage = True

# (bool) Clear previous builds
clean = 0

# (str) Android logcat filters
logcat_filters = python

# (str) Supported architectures (ARM)
android.archs = arm64-v8a, armeabi-v7a

# (bool) Request permissions at runtime
android.allow_backup = True
android.debug = 1

# (str) Package format
android.packaging = apk

# (bool) Allow Internet access
android.internet = True

# (str) Command to start the app on Android
android.entrypoint = org.kivy.android.PythonActivity

# (str) Build command
build_command = release

# (str) Path to keystore (optional for signed build)
# android.release_keystore = safergas.keystore
# android.keyalias = safergas

# (str) Keystore passwords (optional)
# android.release_keyalias_pass = your_password
# android.release_keystore_pass = your_password

[buildozer]
log_level = 2
warn_on_root = 1
