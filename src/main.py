import subprocess
import threading
import tkinter as tk
from tkinter import ttk
import time
import os

# Calculate script_dir and config_path at the module level
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "..", "config", "autoconnect.txt")

class ScrcpyMediaController:
    def __init__(self, master):
        self.master = master
        master.title("Scrcpy Media Controller")

        self.autoconnect_var = tk.BooleanVar()
        self.autoconnect_var.set(False)

        self.ip_entry_label = ttk.Label(master, text="Device IP:")
        self.ip_entry_label.grid(row=0, column=0, padx=5, pady=5)
        self.ip_entry = ttk.Entry(master)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)

        self.autoconnect_check = ttk.Checkbutton(master, text="Remember Me", variable=self.autoconnect_var)
        self.autoconnect_check.grid(row=0, column=3, padx=5, pady=5)

        self.connect_button = ttk.Button(master, text="Connect", command=self.connect)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)

        self.volume_type_label = ttk.Label(master, text="Volume Type:")
        self.volume_type_label.grid(row=1, column=0, padx=5, pady=5)
        self.volume_type_combobox = ttk.Combobox(master, values=["Media", "Call", "Ring", "Alarm", "System"])
        self.volume_type_combobox.grid(row=1, column=1, padx=5, pady=5)
        self.volume_type_combobox.current(0)
        self.volume_type_combobox.bind("<<ComboboxSelected>>", self.update_volume_scale)

        self.volume_label = ttk.Label(master, text="Volume:")
        self.volume_label.grid(row=2, column=0, padx=5, pady=5)
        self.volume_var = tk.IntVar()
        self.volume_scale = ttk.Scale(master, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.volume_var)
        self.volume_scale.grid(row=2, column=1, columnspan=2, padx=5, pady=5)
        self.volume_var.trace_add("write", self.on_volume_change)

        self.play_button = ttk.Button(master, text="Play/Pause", command=self.play_pause)
        self.play_button.grid(row=3, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(master, text="Stop", command=self.stop)
        self.stop_button.grid(row=3, column=1, padx=5, pady=5)

        self.next_button = ttk.Button(master, text="Next", command=self.next_track)
        self.next_button.grid(row=4, column=0, padx=5, pady=5)

        self.prev_button = ttk.Button(master, text="Previous", command=self.prev_track)
        self.prev_button.grid(row=4, column=1, padx=5, pady=5)

        self.debug_text = tk.Text(master, height=5, width=40)
        self.debug_text.grid(row=5, column=0, columnspan=3, padx=5, pady=5)

        self.adb_connected = False
        self.ip_address = None
        self.volume_steps = {"Media": 15, "Call": 7, "Ring": 7, "Alarm": 7, "System": 7}
        self.volume_delay = 0.25
        self.volume_timer = None
        self.pending_volume = None
        self.previous_volume_level = {}

        self.load_autoconnect_ip()

    def load_autoconnect_ip(self):
        try:
            with open(config_path, "r") as f:
                ip = f.read().strip()
                if ip:
                    self.ip_entry.insert(0, ip)
                    self.autoconnect_var.set(True)
                    self.connect()
                else:
                    self.ip_entry.insert(0, "192.168.1.XXX")
                    self.autoconnect_var.set(False)
        except FileNotFoundError:
            self.ip_entry.insert(0, "192.168.1.XXX")

    def save_autoconnect_ip(self):
        if self.autoconnect_var.get():
            with open(config_path, "w") as f:
                f.write(self.ip_entry.get())
        else:
            try:
                os.remove(config_path)
            except FileNotFoundError:
                pass

    def connect(self):
        self.ip_address = self.ip_entry.get()
        self.save_autoconnect_ip()
        threading.Thread(target=self._connect_adb).start()

    def _connect_adb(self):
        try:
            result = subprocess.run(f"adb connect {self.ip_address}:5555", shell=True, check=True, capture_output=True)
            self.adb_connected = True
            self.debug_output(f"Connected to {self.ip_address}")
        except subprocess.CalledProcessError as e:
            self.debug_output(f"Connection failed: {e.stderr.decode()}")

    def on_volume_change(self, *args):
        value = self.volume_var.get()
        self.pending_volume = str(value)
        self.start_volume_timer()

    def start_volume_timer(self):
        if self.volume_timer:
            self.master.after_cancel(self.volume_timer)
        self.volume_timer = self.master.after(int(self.volume_delay * 1000), self.send_volume_command)

    def send_volume_command(self):
        if self.pending_volume is not None:
            threading.Thread(target=self._set_volume_background, args=(self.pending_volume,)).start()
            self.pending_volume = None
        self.volume_timer = None

    def _set_volume_background(self, value):
        if self.adb_connected:
            volume_type = self.volume_type_combobox.get()
            stream_type = {"Media": 3, "Call": 0, "Ring": 2, "Alarm": 4, "System": 1}[volume_type]
            steps = self.volume_steps[volume_type]
            try:
                volume_level = int(float(value) / 100 * steps)
            except ValueError:
                volume_level = 0

            if volume_type in self.previous_volume_level and self.previous_volume_level[volume_type] == volume_level:
                return

            self.previous_volume_level[volume_type] = volume_level

            subprocess.run(f"adb shell media volume --stream {stream_type} --set {volume_level}", shell=True)
            self.debug_output(f"Set {volume_type} volume to {volume_level}")

    def play_pause(self):
        if self.adb_connected:
            subprocess.run("adb shell input keyevent 85", shell=True)
            self.debug_output("Play/Pause")

    def stop(self):
        if self.adb_connected:
            subprocess.run("adb shell input keyevent 86", shell=True)
            self.debug_output("Stop")

    def next_track(self):
        if self.adb_connected:
            subprocess.run("adb shell input keyevent 87", shell=True)
            self.debug_output("Next Track")

    def prev_track(self):
        if self.adb_connected:
            subprocess.run("adb shell input keyevent 88", shell=True)
            self.debug_output("Previous Track")

    def debug_output(self, message):
        self.debug_text.insert(tk.END, message + "\n")
        self.debug_text.see(tk.END)

    def update_volume_scale(self, event=None):
        volume_type = self.volume_type_combobox.get()
        steps = self.volume_steps[volume_type]
        self.volume_scale.destroy()
        self.volume_var = tk.IntVar()
        self.volume_scale = ttk.Scale(self.master, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.volume_var)
        self.volume_scale.grid(row=2, column=1, columnspan=2, padx=5, pady=5)
        self.volume_var.trace_add("write", self.on_volume_change)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScrcpyMediaController(root)
    root.mainloop()