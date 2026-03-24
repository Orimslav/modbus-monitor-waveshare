"""
Modbus IO Monitor & Control
Waveshare Modbus RTU IO 8CH — monitoring and control via Modbus TCP/IP
"""

import tkinter as tk
from tkinter import messagebox
import threading
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# --- Constants ---
DEFAULT_IP = "10.10.10.10"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
REFRESH_INTERVAL_MS = 1000
DI_COUNT = 8
DO_COUNT = 8

COLOR_ON = "#00c853"
COLOR_OFF = "#b0bec5"
COLOR_ERROR = "#f44336"
COLOR_CONNECTED = "#00c853"
COLOR_DISCONNECTED = "#f44336"
COLOR_BG = "#1e1e2e"
COLOR_PANEL = "#2a2a3e"
COLOR_TEXT = "#e0e0e0"
COLOR_LABEL = "#90caf9"
COLOR_BUTTON_ON = "#1b5e20"
COLOR_BUTTON_OFF_CH = "#b71c1c"
COLOR_BUTTON_CONNECT = "#1565c0"
COLOR_BUTTON_DISCONNECT = "#b71c1c"


def _err_msg(exc):
    """Extract error message safely outside lambda."""
    return str(exc)


class ModbusMonitorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Modbus IO Monitor & Control — Waveshare RTU IO 8CH")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        self.client = None
        self.connected = False
        self.slave_id = DEFAULT_SLAVE_ID
        self.refresh_job = None
        self.lock = threading.Lock()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        conn_frame = tk.LabelFrame(
            self.root, text="Connection", bg=COLOR_PANEL, fg=COLOR_LABEL,
            font=("Segoe UI", 10, "bold"), padx=10, pady=8, bd=2, relief="groove"
        )
        conn_frame.grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 6), sticky="ew")

        tk.Label(conn_frame, text="IP:", bg=COLOR_PANEL, fg=COLOR_TEXT).grid(row=0, column=0, sticky="e")
        self.ip_var = tk.StringVar(value=DEFAULT_IP)
        tk.Entry(conn_frame, textvariable=self.ip_var, width=16, bg="#3a3a52", fg=COLOR_TEXT,
                 insertbackground=COLOR_TEXT, relief="flat").grid(row=0, column=1, padx=(4, 12))

        tk.Label(conn_frame, text="Port:", bg=COLOR_PANEL, fg=COLOR_TEXT).grid(row=0, column=2, sticky="e")
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        tk.Entry(conn_frame, textvariable=self.port_var, width=7, bg="#3a3a52", fg=COLOR_TEXT,
                 insertbackground=COLOR_TEXT, relief="flat").grid(row=0, column=3, padx=(4, 12))

        tk.Label(conn_frame, text="Slave ID:", bg=COLOR_PANEL, fg=COLOR_TEXT).grid(row=0, column=4, sticky="e")
        self.slave_var = tk.StringVar(value=str(DEFAULT_SLAVE_ID))
        tk.Entry(conn_frame, textvariable=self.slave_var, width=5, bg="#3a3a52", fg=COLOR_TEXT,
                 insertbackground=COLOR_TEXT, relief="flat").grid(row=0, column=5, padx=(4, 16))

        self.connect_btn = tk.Button(
            conn_frame, text="Connect", width=12,
            bg=COLOR_BUTTON_CONNECT, fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            command=self._toggle_connection
        )
        self.connect_btn.grid(row=0, column=6, padx=4)

        self.status_canvas = tk.Canvas(conn_frame, width=16, height=16,
                                       bg=COLOR_PANEL, highlightthickness=0)
        self.status_canvas.grid(row=0, column=7, padx=(8, 2))
        self.status_dot = self.status_canvas.create_oval(2, 2, 14, 14,
                                                         fill=COLOR_DISCONNECTED, outline="")

        self.status_label = tk.Label(conn_frame, text="Disconnected", bg=COLOR_PANEL,
                                     fg=COLOR_DISCONNECTED, font=("Segoe UI", 9))
        self.status_label.grid(row=0, column=8, padx=(0, 6))

        # DI panel
        di_frame = tk.LabelFrame(
            self.root, text="Digital Inputs  (FC02 — read only)",
            bg=COLOR_PANEL, fg=COLOR_LABEL,
            font=("Segoe UI", 10, "bold"), padx=10, pady=10, bd=2, relief="groove"
        )
        di_frame.grid(row=1, column=0, padx=(12, 6), pady=6, sticky="nsew")

        self.di_indicators = []
        self.di_labels = []
        for i in range(DI_COUNT):
            ch_frame = tk.Frame(di_frame, bg=COLOR_PANEL)
            ch_frame.grid(row=i, column=0, pady=3, sticky="ew")

            tk.Label(ch_frame, text=f"DI {i + 1}", width=6,
                     bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w",
                     font=("Segoe UI", 9)).pack(side="left")

            canvas = tk.Canvas(ch_frame, width=40, height=22,
                               bg=COLOR_PANEL, highlightthickness=0)
            canvas.pack(side="left", padx=(4, 6))
            rect = canvas.create_rectangle(2, 2, 38, 20, fill=COLOR_OFF, outline="")

            lbl = tk.Label(ch_frame, text="OFF", width=4,
                           bg=COLOR_PANEL, fg=COLOR_TEXT,
                           font=("Segoe UI", 9, "bold"))
            lbl.pack(side="left")

            self.di_indicators.append((canvas, rect))
            self.di_labels.append(lbl)

        # DO panel
        do_frame = tk.LabelFrame(
            self.root, text="Digital Outputs  (FC05 — write / FC01 — read state)",
            bg=COLOR_PANEL, fg=COLOR_LABEL,
            font=("Segoe UI", 10, "bold"), padx=10, pady=10, bd=2, relief="groove"
        )
        do_frame.grid(row=1, column=1, padx=(6, 12), pady=6, sticky="nsew")

        self.do_indicators = []
        self.do_state_labels = []

        for i in range(DO_COUNT):
            ch_frame = tk.Frame(do_frame, bg=COLOR_PANEL)
            ch_frame.grid(row=i, column=0, pady=3, sticky="ew")

            tk.Label(ch_frame, text=f"DO {i + 1}", width=6,
                     bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w",
                     font=("Segoe UI", 9)).pack(side="left")

            canvas = tk.Canvas(ch_frame, width=40, height=22,
                               bg=COLOR_PANEL, highlightthickness=0)
            canvas.pack(side="left", padx=(4, 6))
            rect = canvas.create_rectangle(2, 2, 38, 20, fill=COLOR_OFF, outline="")

            lbl = tk.Label(ch_frame, text="OFF", width=4,
                           bg=COLOR_PANEL, fg=COLOR_TEXT,
                           font=("Segoe UI", 9, "bold"))
            lbl.pack(side="left")

            tk.Button(
                ch_frame, text="ON", width=5,
                bg=COLOR_BUTTON_ON, fg="white", relief="flat",
                font=("Segoe UI", 8, "bold"), cursor="hand2",
                command=lambda ch=i: self._set_do(ch, True)
            ).pack(side="left", padx=(6, 2))

            tk.Button(
                ch_frame, text="OFF", width=5,
                bg=COLOR_BUTTON_OFF_CH, fg="white", relief="flat",
                font=("Segoe UI", 8, "bold"), cursor="hand2",
                command=lambda ch=i: self._set_do(ch, False)
            ).pack(side="left", padx=2)

            self.do_indicators.append((canvas, rect))
            self.do_state_labels.append(lbl)

        # Status bar
        self.statusbar = tk.Label(
            self.root, text="Ready.", anchor="w",
            bg="#12121e", fg="#78909c",
            font=("Segoe UI", 8), padx=8, pady=4
        )
        self.statusbar.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _toggle_connection(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        ip = self.ip_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
            slave_id = int(self.slave_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Port and Slave ID must be integers.")
            return

        self._set_status("Connecting…", "#ffa726")
        self.connect_btn.config(state="disabled")

        def do_connect():
            try:
                c = ModbusTcpClient(ip, port=port, timeout=3)
                if not c.connect():
                    raise ConnectionError(f"Cannot connect to {ip}:{port}")
                with self.lock:
                    self.client = c
                    self.slave_id = slave_id
                    self.connected = True
                self.root.after(0, self._on_connected)
            except Exception as exc:
                error_text = str(exc)
                self.root.after(0, lambda: self._on_connect_error(error_text))

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_connected(self):
        self._set_status("Connected", COLOR_CONNECTED)
        self.connect_btn.config(text="Disconnect", state="normal",
                                bg=COLOR_BUTTON_DISCONNECT)
        self._set_statusbar(
            f"Connected to {self.ip_var.get()}:{self.port_var.get()}  |  Slave ID {self.slave_id}"
        )
        self._start_refresh()

    def _on_connect_error(self, message):
        self.connected = False
        self._set_status("Disconnected", COLOR_DISCONNECTED)
        self.connect_btn.config(text="Connect", state="normal", bg=COLOR_BUTTON_CONNECT)
        self._set_statusbar(f"Connection error: {message}")
        messagebox.showerror("Connection Error", message)

    def _disconnect(self):
        self._stop_refresh()
        with self.lock:
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
                self.client = None
            self.connected = False
        self._set_status("Disconnected", COLOR_DISCONNECTED)
        self.connect_btn.config(text="Connect", bg=COLOR_BUTTON_CONNECT)
        self._set_statusbar("Disconnected.")
        self._reset_indicators()

    # ------------------------------------------------------------------
    # Auto-refresh
    # ------------------------------------------------------------------

    def _start_refresh(self):
        self._refresh_cycle()

    def _stop_refresh(self):
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
            self.refresh_job = None

    def _refresh_cycle(self):
        threading.Thread(target=self._poll, daemon=True).start()
        self.refresh_job = self.root.after(REFRESH_INTERVAL_MS, self._refresh_cycle)

    def _poll(self):
        with self.lock:
            client = self.client
            slave_id = self.slave_id

        if client is None or not self.connected:
            return

        try:
            di_result = client.read_discrete_inputs(0, count=DI_COUNT, device_id=slave_id)
            if di_result.isError():
                raise ModbusException("FC02 read error")
            di_states = list(di_result.bits[:DI_COUNT])

            do_result = client.read_coils(0, count=DO_COUNT, device_id=slave_id)
            if do_result.isError():
                raise ModbusException("FC01 read error")
            do_states = list(do_result.bits[:DO_COUNT])

            self.root.after(0, lambda: self._update_di(di_states))
            self.root.after(0, lambda: self._update_do_state(do_states))
            ip = self.ip_var.get()
            port = self.port_var.get()
            self.root.after(0, lambda: self._set_statusbar(
                f"Last refresh OK  |  {ip}:{port}  |  Slave ID {slave_id}"
            ))

        except Exception as exc:
            error_text = str(exc)
            self.root.after(0, lambda: self._handle_comm_error(error_text))

    # ------------------------------------------------------------------
    # DO write
    # ------------------------------------------------------------------

    def _set_do(self, channel, state):
        if not self.connected:
            self._set_statusbar("Not connected.")
            return

        def do_write():
            with self.lock:
                client = self.client
                slave_id = self.slave_id
            if client is None:
                return
            try:
                result = client.write_coil(channel, state, device_id=slave_id)
                if result.isError():
                    raise ModbusException(f"FC05 write error on DO {channel + 1}")
                label = "ON" if state else "OFF"
                self.root.after(0, lambda: self._set_statusbar(
                    f"DO {channel + 1} set to {label}"
                ))
            except Exception as exc:
                error_text = str(exc)
                self.root.after(0, lambda: self._handle_comm_error(error_text))

        threading.Thread(target=do_write, daemon=True).start()

    # ------------------------------------------------------------------
    # UI update helpers
    # ------------------------------------------------------------------

    def _update_di(self, states):
        for i, (canvas, rect) in enumerate(self.di_indicators):
            active = states[i] if i < len(states) else False
            canvas.itemconfig(rect, fill=COLOR_ON if active else COLOR_OFF)
            self.di_labels[i].config(
                text="ON" if active else "OFF",
                fg=COLOR_ON if active else COLOR_TEXT
            )

    def _update_do_state(self, states):
        for i, (canvas, rect) in enumerate(self.do_indicators):
            active = states[i] if i < len(states) else False
            canvas.itemconfig(rect, fill=COLOR_ON if active else COLOR_OFF)
            self.do_state_labels[i].config(
                text="ON" if active else "OFF",
                fg=COLOR_ON if active else COLOR_TEXT
            )

    def _reset_indicators(self):
        for canvas, rect in self.di_indicators:
            canvas.itemconfig(rect, fill=COLOR_OFF)
        for lbl in self.di_labels:
            lbl.config(text="OFF", fg=COLOR_TEXT)
        for canvas, rect in self.do_indicators:
            canvas.itemconfig(rect, fill=COLOR_OFF)
        for lbl in self.do_state_labels:
            lbl.config(text="OFF", fg=COLOR_TEXT)

    def _set_status(self, text, color):
        self.status_canvas.itemconfig(self.status_dot, fill=color)
        self.status_label.config(text=text, fg=color)

    def _set_statusbar(self, text):
        self.statusbar.config(text=text)

    def _handle_comm_error(self, message):
        self._set_statusbar(f"Error: {message}")
        self._set_status("Error", COLOR_ERROR)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _on_close(self):
        self._stop_refresh()
        with self.lock:
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
        self.root.destroy()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    root = tk.Tk()
    root.minsize(700, 380)
    ModbusMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
