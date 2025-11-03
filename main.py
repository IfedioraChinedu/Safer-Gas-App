# Safer Gas App
# Author: Chinedu Ifediora (IMAXEUNO)

from kivy.config import Config
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '800')

from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.storage.jsonstore import JsonStore
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.uix.screenmanager import ScreenManager, Screen

from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.list import OneLineListItem
from kivymd.uix.snackbar import Snackbar

import os, csv, io, time, queue, threading, traceback

# Graph
from kivy_garden.graph import Graph, MeshLinePlot

# Platform check
from kivy.utils import platform
ANDROID = platform == "android"

if ANDROID:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
else:
    import serial
    import serial.tools.list_ports

APP_NAME = "Safer Gas"
LOG_CSV = "safergas_logs.csv"
EVENT_LOG = "safergas_events.txt"
STORE_FILE = "safergas_settings.json"
AUTO_UPDATE_INTERVAL = 900  # seconds = 15 minutes (change 600-1200 allowed)

KV = '''
MDScreen:
    md_bg_color: 0,0,0,1

    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(8)

        MDBoxLayout:
            size_hint_y: None
            height: dp(56)
            MDLabel:
                text: app.app_title
                font_style: "H5"
                theme_text_color: "Custom"
                text_color: app.green_text
            MDRaisedButton:
                id: btn_connect
                text: "Devices"
                md_bg_color: app.green
                size_hint_x: None
                width: dp(110)
                on_release: app.open_device_list()

        MDCard:
            size_hint_y: None
            height: dp(170)
            md_bg_color: 0,0,0,1
            elevation: 8
            padding: dp(12)
            BoxLayout:
                orientation: 'vertical'
                MDLabel:
                    text: "Remaining Gas"
                    theme_text_color: "Custom"
                    text_color: app.green_text
                MDLabel:
                    id: weight_lbl
                    text: app.weight_display
                    font_style: "H3"
                    halign: "left"
                MDBoxLayout:
                    size_hint_y: None
                    height: dp(28)
                    MDLabel:
                        text: "Cylinder Status:"
                        theme_text_color: "Custom"
                        text_color: app.green_text
                    MDLabel:
                        id: status_lbl
                        text: app.status_text
                        theme_text_color: "Custom"
                        text_color: app.status_color

        MDBoxLayout:
            size_hint_y: None
            height: dp(56)
            spacing: dp(8)
            MDRaisedButton:
                text: "Calibrate"
                md_bg_color: app.green
                on_release: app.calibrate_pressed()
            MDRaisedButton:
                text: "Disconnect"
                md_bg_color: app.green
                on_release: app.disconnect_device()
            MDRaisedButton:
                text: "Settings"
                md_bg_color: app.green
                on_release: app.open_settings()

        MDCard:
            md_bg_color: 0,0,0,1
            elevation: 4
            padding: dp(8)
            BoxLayout:
                orientation: 'vertical'
                Graph:
                    id: graph
                    xlabel: "Samples"
                    ylabel: "Weight (kg)"
                    x_ticks_major: 1
                    y_ticks_major: 1
                    xmin: 0
                    xmax: 10
                    ymin: 0
                    ymax: 50
                BoxLayout:
                    size_hint_y: None
                    height: dp(8)

        MDCard:
            size_hint_y: None
            height: dp(120)
            padding: dp(12)
            md_bg_color: 0,0,0,1
            BoxLayout:
                orientation: 'vertical'
                MDLabel:
                    text: "Tip of the Day"
                    theme_text_color: "Custom"
                    text_color: app.green_text
                    font_style: "Subtitle1"
                MDLabel:
                    id: tip_lbl
                    text: app.tip_of_day
                    theme_text_color: "Primary"
'''

# ---------------- CommManager (BT/Serial safe threading) ----------------
class CommManager:
    def __init__(self, rx_queue, app):
        self.rx_queue = rx_queue
        self.app = app
        self.thread = None
        self.running = False
        self.serial = None  # pyserial Serial (desktop)
        self.sock = None    # Java socket (Android)
        self.connected = False
        self.lock = threading.Lock()

    # Desktop serial connect (port string)
    def connect_serial(self, port=None, baud=115200):
        try:
            if port is None:
                ports = list(serial.tools.list_ports.comports())
                if not ports:
                    return False, "No serial ports"
                port = ports[0].device
            self.serial = serial.Serial(port, baudrate=baud, timeout=0.5)
            self.running = True
            self.thread = threading.Thread(target=self._serial_loop, daemon=True)
            self.thread.start()
            self.connected = True
            return True, f"Serial {port}"
        except Exception as e:
            return False, str(e)

    def _serial_loop(self):
        try:
            while self.running and self.serial and self.serial.is_open:
                try:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self.rx_queue.put(line)
                    else:
                        time.sleep(0.05)
                except Exception:
                    time.sleep(0.05)
        except Exception as e:
            self.rx_queue.put(f"BT_ERROR:{e}")
            self.connected = False

    # Android BT connect by chosen device (name or address)
    def connect_bt_by_device(self, bt_device):
        # bt_device: either Java BluetoothDevice or (name, address) tuple on desktop
        try:
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            UUID = autoclass('java.util.UUID')
            adapter = BluetoothAdapter.getDefaultAdapter()
            if not adapter or not adapter.isEnabled():
                return False, "Bluetooth adapter unavailable or disabled"
            # find by address or name
            paired = adapter.getBondedDevices().toArray()
            target = None
            for dev in paired:
                if dev.getAddress() == bt_device or dev.getName() == bt_device:
                    target = dev
                    break
            if not target:
                return False, "Device not paired"
            spp_uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
            sock = target.createRfcommSocketToServiceRecord(spp_uuid)
            sock.connect()
            self.sock = sock
            self.running = True
            self.thread = threading.Thread(target=self._android_loop, daemon=True)
            self.thread.start()
            self.connected = True
            return True, "Connected BT"
        except Exception as e:
            return False, str(e)

    def _android_loop(self):
        try:
            is_ = self.sock.getInputStream()
            buf = bytearray(1024)
            while self.running:
                try:
                    available = is_.available()
                    if available > 0:
                        read = is_.read(buf, 0, min(available, 1024))
                        data = bytes(buf[:read]).decode('utf-8', errors='ignore')
                        for line in data.splitlines():
                            line = line.strip()
                            if line:
                                self.rx_queue.put(line)
                    else:
                        time.sleep(0.05)
                except Exception:
                    time.sleep(0.05)
        except Exception as e:
            self.rx_queue.put(f"BT_ERROR:{e}")
            self.connected = False

    # send a line (thread-safe)
    def send_line(self, s):
        try:
            with self.lock:
                if self.serial and self.serial.is_open:
                    self.serial.write((s + "\n").encode('utf-8'))
                    return True
                if self.sock:
                    out = self.sock.getOutputStream()
                    out.write((s + "\n").encode('utf-8'))
                    out.flush()
                    return True
        except Exception as e:
            self.rx_queue.put(f"BT_ERROR:{e}")
        return False

    def disconnect(self):
        self.running = False
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
        except:
            pass
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        self.connected = False

# ---------------- SaferGasApp ----------------
class SaferGasApp(MDApp):
    app_title = StringProperty(APP_NAME)
    weight_display = StringProperty("0.00 kg")
    status_text = StringProperty("OK")
    status_color = ListProperty([0, 1, 0, 1])
    green = ListProperty([0, 0.9, 0.15, 1])
    green_text = ListProperty([0.6, 1, 0.6, 1])
    tip_of_day = StringProperty("")
    auto_interval = NumericProperty(AUTO_UPDATE_INTERVAL)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rxq = queue.Queue()
        self.comm = CommManager(self.rxq, self)
        self.store = None
        self.log_path = None
        self.event_log = None
        self.graph_plot = None
        self.latest = {"weight": 0.0, "gasv": 0.0, "status": "OK"}
        self._incoming_mode = False
        self._incoming_buf = []
        self.tips = [
            "Always turn off your gas regulator after cooking.",
            "Check your gas hose for cracks or aging every two weeks.",
            "Keep your cylinder outside your kitchen in a well-ventilated area.",
            "Avoid placing flammable items near your gas burner.",
            "Clean your burner holes regularly to ensure steady flames.",
            "Ensure your gas detector is clean and free from dust.",
            "Store the cylinder upright; never lie it on its side.",
            "If you smell gas, turn off the regulator immediately and ventilate the area.",
            "Do not modify gas fittings without professional help.",
            "Monitor daily gas usage to detect leaks or waste early."
        ]

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Green"
        self.root = Builder.load_string(KV)
        self.store = JsonStore(os.path.join(self.user_data_dir, STORE_FILE))
        self.log_path = os.path.join(self.user_data_dir, LOG_CSV)
        self.event_log = os.path.join(self.user_data_dir, EVENT_LOG)
        os.makedirs(self.user_data_dir, exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Entry", "Weight(kg)", "GasV", "Status"])
        if not os.path.exists(self.event_log):
            open(self.event_log, "a").close()
        # init graph
        g = self.root.ids.graph
        self.graph_plot = MeshLinePlot(color=[0, 1, 0, 1])
        self.graph_plot.points = []
        g.add_plot(self.graph_plot)
        # set tip of day (simple deterministic rotation)
        self.tip_of_day = self._get_tip_of_day()
        # schedule queue processing
        Clock.schedule_interval(self.process_rx_queue, 0.2)
        # request android perms
        if ANDROID:
            try:
                request_permissions([Permission.BLUETOOTH, Permission.BLUETOOTH_ADMIN, Permission.ACCESS_FINE_LOCATION])
            except Exception:
                pass
        return self.root

    def _get_tip_of_day(self):
        day = time.localtime().tm_mday
        return self.tips[day % len(self.tips)]

    # ---------------- device UI ----------------
    def open_device_list(self):
        items = []
        if ANDROID:
            try:
                BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
                adapter = BluetoothAdapter.getDefaultAdapter()
                paired = []
                if adapter:
                    paired = adapter.getBondedDevices().toArray()
                for dev in paired:
                    name = dev.getName()
                    addr = dev.getAddress()
                    items.append((name, addr))
            except Exception as e:
                self._append_event(f"BT list error: {e}")
        else:
            try:
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    items.append((p.device, p.device))
            except Exception as e:
                self._append_event(f"Serial list error: {e}")

        # build dialog items
        menu_items = []
        for name, addr in items:
            menu_items.append(OneLineListItem(text=f"{name} ({addr})", on_release=lambda inst, n=name, a=addr: self._on_device_selected(n, a)))
        if not menu_items:
            Snackbar(text="No paired devices or serial ports found").open()
            return
        self.device_dialog = MDDialog(title="Select device", type="simple", items=menu_items, size_hint=(0.9, 0.8))
        self.device_dialog.open()

    def _on_device_selected(self, name, addr):
        try:
            if hasattr(self, "device_dialog") and self.device_dialog:
                self.device_dialog.dismiss()
            self._append_event(f"Connecting to {name} ({addr})")
            if ANDROID:
                ok, msg = self.comm.connect_bt_by_device(addr)
            else:
                ok, msg = self.comm.connect_serial(addr)
            self._append_event(str(msg))
            if ok:
                Snackbar(text="Connected").open()
                # do connect actions on background thread
                threading.Thread(target=self._on_connected_worker, daemon=True).start()
            else:
                Snackbar(text=f"Connect failed: {msg}").open()
        except Exception as e:
            self._append_event(f"Device select error: {e}")

    def _on_connected_worker(self):
        # small delay
        time.sleep(0.5)
        # request SD upload and an immediate latest; schedule periodic updates
        try:
            if self.comm.connected:
                self._append_event("Requesting SD upload...")
                self.comm.send_line("UPLOAD_SD")
                time.sleep(0.2)
                self.comm.send_line("GET_LATEST")
                # schedule periodic auto updates
                Clock.schedule_interval(lambda dt: threading.Thread(target=self._auto_get_latest, daemon=True).start(), self.auto_interval)
        except Exception as e:
            self._append_event(f"Connected worker error: {e}")

    def _auto_get_latest(self):
        try:
            if self.comm.connected:
                self._append_event("Auto GET_LATEST")
                self.comm.send_line("GET_LATEST")
        except Exception as e:
            self._append_event(f"AUTO GET error: {e}")

    def disconnect_device(self):
        try:
            self.comm.disconnect()
            self._append_event("Disconnected by user")
            Snackbar(text="Disconnected").open()
        except Exception as e:
            self._append_event(f"Disconnect error: {e}")

    # ---------------- calibrate ----------------
    def calibrate_pressed(self):
        yes = MDFlatButton(text="YES", on_release=lambda *a: self._confirm_calibrate(True))
        no = MDFlatButton(text="NO", on_release=lambda *a: self._confirm_calibrate(False))
        self.cal_dialog = MDDialog(title="Calibrate (Reset Tare)", text="Set current mass as tare (zero)?", size_hint=(0.8, None), height=dp(160), buttons=[no, yes])
        self.cal_dialog.open()

    def _confirm_calibrate(self, ok):
        try:
            if hasattr(self, "cal_dialog") and self.cal_dialog:
                self.cal_dialog.dismiss()
            if ok:
                if self.comm.connected:
                    # send in background
                    threading.Thread(target=lambda: self.comm.send_line("SET_TARE"), daemon=True).start()
                    self._append_event("Sent SET_TARE")
                    Snackbar(text="Calibrate command sent").open()
                else:
                    Snackbar(text="Not connected").open()
        except Exception as e:
            self._append_event(f"Calibrate error: {e}")

    # ---------------- incoming processing ----------------
    def process_rx_queue(self, dt):
        while not self.rxq.empty():
            line = self.rxq.get_nowait()
            self._handle_line(line)

    def _handle_line(self, line):
        try:
            self._append_event(f"RX: {line}")
            if line.startswith("REQUEST_TARE:"):
                try:
                    val = float(line.split(":", 1)[1])
                except:
                    val = None
                # confirm device-initiated tare
                self._open_device_tare_confirm(val)
                return
            if line.startswith("LATEST,"):
                parts = line.split(",")
                if len(parts) >= 4:
                    try:
                        w = float(parts[1]); g = float(parts[2]); st = parts[3]
                        self._add_reading(w, g, st)
                    except Exception:
                        self._append_event("LATEST parse error")
                return
            if line == "BEGIN_LOG":
                self._incoming_mode = True
                self._incoming_buf = []
                return
            if line == "END_LOG":
                self._incoming_mode = False
                threading.Thread(target=self._save_incoming_log, args=(self._incoming_buf,), daemon=True).start()
                self._incoming_buf = []
                return
            if self._incoming_mode:
                self._incoming_buf.append(line)
                return
            if line.startswith("TARE_SET_OK"):
                Snackbar(text="Tare set on device").open()
                return
            if line.startswith("BT_ERROR:"):
                self._append_event("BT_ERROR: " + line.split(":", 1)[1])
                Snackbar(text="Bluetooth error").open()
        except Exception as e:
            self._append_event("Handle line exception: " + str(e))

    def _open_device_tare_confirm(self, val):
        txt = f"Device requests: set tare to {val:.2f} kg. Confirm?"
        yes = MDFlatButton(text="YES", on_release=lambda *a: self._on_device_tare_confirm(True))
        no = MDFlatButton(text="NO", on_release=lambda *a: self._on_device_tare_confirm(False))
        self.td = MDDialog(title="Device Tare Request", text=txt, size_hint=(0.8, None), height=dp(180), buttons=[no, yes])
        self.td.open()

    def _on_device_tare_confirm(self, ok):
        try:
            if hasattr(self, "td") and self.td:
                self.td.dismiss()
            if ok and self.comm.connected:
                threading.Thread(target=lambda: self.comm.send_line("SET_TARE"), daemon=True).start()
                self._append_event("Confirmed device tare -> SET_TARE sent")
                Snackbar(text="Confirmed tare").open()
            else:
                self._append_event("Device tare canceled")
        except Exception as e:
            self._append_event("Device tare confirm error: " + str(e))

    # ---------------- add reading & plot ----------------
    def _add_reading(self, weight, gasv, status):
        try:
            # append to CSV safely
            entry_idx = 1
            if os.path.exists(self.log_path):
                with open(self.log_path, "r", encoding="utf-8") as f:
                    entry_idx = sum(1 for _ in f)
            with open(self.log_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([entry_idx, f"{weight:.2f}", f"{gasv:.3f}", status])
            # update latest and UI
            self.latest = {"weight": weight, "gasv": gasv, "status": status}
            self._update_ui()
            # append graph point
            threading.Thread(target=lambda: self._append_graph_point(weight), daemon=True).start()
        except Exception as e:
            self._append_event("Add reading error: " + str(e))

    def _append_graph_point(self, weight):
        try:
            g = self.root.ids.graph
            pts = list(self.graph_plot.points) if getattr(self.graph_plot, "points", None) else []
            pts.append((len(pts), float(weight)))
            self.graph_plot.points = pts
            g.xmax = max(10, len(pts))
            g.ymax = max(max([p[1] for p in pts]) + 1, 1) if pts else 10
            g.ymin = min(0, min([p[1] for p in pts]) - 1 if pts else 0)
        except Exception as e:
            self._append_event("Graph append error: " + str(e))

    def _save_incoming_log(self, lines):
        try:
            csv_text = "\n".join(lines)
            df = None
            try:
                import pandas as pd
                df = pd.read_csv(io.StringIO(csv_text))
                df.to_csv(self.log_path, index=False)
                self._append_event(f"Saved {len(df)} rows from SD")
                # rebuild graph
                weights = []
                if 'Weight(kg)' in df.columns:
                    weights = df['Weight(kg)'].astype(float).tolist()
                else:
                    weights = df.iloc[:, 1].astype(float).tolist()
                pts = [(i, float(weights[i])) for i in range(len(weights))]
                self.graph_plot.points = pts
                g = self.root.ids.graph
                g.xmax = max(10, len(pts))
                g.ymax = max(max(weights) + 1, 1) if weights else 10
            except Exception:
                # fallback to csv module parsing
                rdr = csv.reader(io.StringIO(csv_text))
                rows = list(rdr)
                if rows and rows[0] and rows[0][0].lower().startswith("entry"):
                    # write raw rows
                    with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                        w = csv.writer(f)
                        for r in rows:
                            w.writerow(r)
                    self._append_event(f"Saved {len(rows)-1} rows from SD (fallback)")
        except Exception as e:
            self._append_event("Save incoming log error: " + str(e))

    def _update_ui(self):
        try:
            weight = self.latest.get("weight", 0.0)
            status = self.latest.get("status", "OK")
            # animate weight
            try:
                current = float(self.weight_display.split()[0])
            except:
                current = weight
            steps = 12
            for i in range(1, steps + 1):
                Clock.schedule_once(lambda dt, i=i: self._set_weight_interp(current, weight, steps, i), i * 0.03)
            # status color
            if status == "LEAK":
                self.status_text = "LEAK"
                self.status_color = [1, 0.18, 0.18, 1]
            elif status == "LOW":
                self.status_text = "LOW"
                self.status_color = [1, 0.7, 0.15, 1]
            else:
                self.status_text = "OK"
                self.status_color = [0.15, 1, 0.15, 1]
        except Exception as e:
            self._append_event("_update_ui error: " + str(e))

    def _set_weight_interp(self, start, end, steps, i):
        v = start + (end - start) * (i / steps)
        self.weight_display = f"{v:.2f} kg"

    # ---------------- event log ----------------
    def _append_event(self, txt):
        try:
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.event_log, "a", encoding="utf-8") as f:
                f.write(f"[{t}] {txt}\n")
        except Exception:
            pass

    # ---------------- settings ----------------
    def open_settings(self):
        view_logs = MDFlatButton(text="View Data Log", on_release=lambda *a: self._view_data_log())
        view_events = MDFlatButton(text="View Event Log", on_release=lambda *a: self._view_event_log())
        delete_logs = MDFlatButton(text="Delete Logs", on_release=lambda *a: self._confirm_delete_logs())
        theme_toggle = MDFlatButton(text="Toggle Theme", on_release=lambda *a: self._toggle_theme())
        clear_tare = MDFlatButton(text="Clear Tare", on_release=lambda *a: self._clear_tare())
        close = MDFlatButton(text="Close", on_release=lambda *a: self._close_settings())
        self.settings_dialog = MDDialog(title="Settings", text="Choose action", size_hint=(0.9, 0.8),
                                        buttons=[view_logs, view_events, delete_logs, theme_toggle, clear_tare, close])
        self.settings_dialog.open()

    def _view_data_log(self):
        try:
            self.settings_dialog.dismiss()
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.read()[-8000:]
            dlg = MDDialog(title="Data Log (tail)", text=lines if lines else "No data yet", size_hint=(0.95, 0.95), buttons=[MDFlatButton(text="Close", on_release=lambda *a: dlg.dismiss())])
            dlg.open()
        except Exception as e:
            self._append_event("_view_data_log error: " + str(e))

    def _view_event_log(self):
        try:
            self.settings_dialog.dismiss()
            with open(self.event_log, "r", encoding="utf-8") as f:
                txt = f.read()[-8000:]
            dlg = MDDialog(title="Event Log (tail)", text=txt if txt else "No events", size_hint=(0.95, 0.95), buttons=[MDFlatButton(text="Close", on_release=lambda *a: dlg.dismiss())])
            dlg.open()
        except Exception as e:
            self._append_event("_view_event_log error: " + str(e))

    def _confirm_delete_logs(self):
        self.settings_dialog.dismiss()
        yes = MDFlatButton(text="YES", on_release=lambda *a: self._delete_logs_confirmed(True))
        no = MDFlatButton(text="NO", on_release=lambda *a: self._delete_logs_confirmed(False))
        self.del_dialog = MDDialog(title="Delete logs", text="Delete data and event logs? This cannot be undone.", size_hint=(0.8, None), height=dp(180), buttons=[no, yes])
        self.del_dialog.open()

    def _delete_logs_confirmed(self, confirmed):
        try:
            if hasattr(self, "del_dialog") and self.del_dialog:
                self.del_dialog.dismiss()
            if confirmed:
                with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Entry", "Weight(kg)", "GasV", "Status"])
                open(self.event_log, "w", encoding="utf-8").close()
                self._append_event("Logs cleared by user")
                Snackbar(text="Logs deleted").open()
        except Exception as e:
            self._append_event("_delete_logs_confirmed error: " + str(e))

    def _toggle_theme(self):
        try:
            # schedule to avoid layout conflicts
            new_theme = "Light" if self.theme_cls.theme_style == "Dark" else "Dark"
            Clock.schedule_once(lambda dt: setattr(self.theme_cls, "theme_style", new_theme), 0.15)
            self.settings_dialog.dismiss()
            Snackbar(text="Theme changed").open()
        except Exception as e:
            self._append_event("_toggle_theme error: " + str(e))

    def _clear_tare(self):
        try:
            self.settings_dialog.dismiss()
            if self.comm.connected:
                threading.Thread(target=lambda: self.comm.send_line("CLEAR_TARE"), daemon=True).start()
                self._append_event("Sent CLEAR_TARE")
                Snackbar(text="Clear tare sent").open()
            else:
                Snackbar(text="Not connected").open()
        except Exception as e:
            self._append_event("_clear_tare error: " + str(e))

# ---------------- Run ----------------
if __name__ == "__main__":
    SaferGasApp().run()
