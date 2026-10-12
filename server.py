import http.server
import socketserver
import json
import threading
import time
import ctypes
import websockets
import asyncio
import os
import sys
import tkinter as tk
from pynput import mouse
import pystray
from PIL import Image

state = {
    "keys": {},
    "mouse": {
        "buttons": {"M1": False, "M2": False, "M3": False},
        "scrollUp": False,
        "scrollDown": False,
        "x": 50.0,
        "y": 50.0
    }
}
connected_clients = set()

VK_CODES = {
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35, "6": 0x36,
    "t": 0x54, "y": 0x59,
    "tab": 0x09,
    "q": 0x51, "w": 0x57, "e": 0x45, "r": 0x52, "g": 0x47, "h": 0x48,
    "shift": 0x10,
    "a": 0x41, "s": 0x53, "d": 0x44, "f": 0x46,
    "ctrl": 0x11, "alt": 0x12, "space": 0x20,
    "z": 0x5A, "x": 0x58, "c": 0x43, "v": 0x56, "b": 0x42
}

virtual_mouse = {"x": 50.0, "y": 50.0}
last_move_time = time.time()

# 1. Опрос ввода
def input_poll_loop():
    global virtual_mouse, last_move_time
    user32 = ctypes.windll.user32

    while True:
        for key_name, vk_code in VK_CODES.items():
            state["keys"][key_name] = bool(user32.GetAsyncKeyState(vk_code) & 0x8000)

        state["mouse"]["buttons"]["M1"] = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        state["mouse"]["buttons"]["M2"] = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
        state["mouse"]["buttons"]["M3"] = bool(user32.GetAsyncKeyState(0x04) & 0x8000)

        if time.time() - last_move_time > 0.15:
            virtual_mouse["x"] += (50.0 - virtual_mouse["x"]) * 0.15
            virtual_mouse["y"] += (50.0 - virtual_mouse["y"]) * 0.15

        state["mouse"]["x"] = round(virtual_mouse["x"], 2)
        state["mouse"]["y"] = round(virtual_mouse["y"], 2)

        time.sleep(0.01)

threading.Thread(target=input_poll_loop, daemon=True).start()

# 2. Ловим дельты мыши
last_raw_x = None
last_raw_y = None

def on_raw_move(x, y):
    global virtual_mouse, last_raw_x, last_raw_y, last_move_time
    last_move_time = time.time()

    if last_raw_x is not None and last_raw_y is not None:
        dx = x - last_raw_x
        dy = y - last_raw_y
        sensitivity = 0.8

        virtual_mouse["x"] = max(5.0, min(95.0, virtual_mouse["x"] + dx * sensitivity))
        virtual_mouse["y"] = max(5.0, min(95.0, virtual_mouse["y"] + dy * sensitivity))

    last_raw_x = x
    last_raw_y = y

def on_scroll(x, y, dx, dy):
    state["mouse"]["scrollUp"] = dy > 0
    state["mouse"]["scrollDown"] = dy < 0
    def reset_scroll():
        time.sleep(0.1)
        state["mouse"]["scrollUp"] = False
        state["mouse"]["scrollDown"] = False
    threading.Thread(target=reset_scroll, daemon=True).start()

mouse.Listener(on_move=on_raw_move, on_scroll=on_scroll).start()

# 3. HTTP Сервер
def start_http():
    PORT = 8080
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=start_http, daemon=True).start()

# 4. WebSocket Сервер
async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            pass
    except:
        pass
    finally:
        connected_clients.remove(websocket)

async def broadcast_loop():
    while True:
        if connected_clients:
            data = json.dumps(state)
            await asyncio.gather(*[client.send(data) for client in connected_clients], return_exceptions=True)
        await asyncio.sleep(0.01)

def run_asyncio_loop():
    async def main():
        async with websockets.serve(ws_handler, "localhost", 8765):
            await broadcast_loop()
    asyncio.run(main())

threading.Thread(target=run_asyncio_loop, daemon=True).start()

# 5. Трей и иконка
tray_icon = None

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def quit_app(icon, item):
    icon.stop()
    os._exit(0)

def show_window(icon, item):
    icon.stop()
    # Возвращаем окно на экран и выводим на передний план
    root.after(0, lambda: [root.deiconify(), root.lift(), root.focus_force()])

def setup_tray():
    global tray_icon
    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        image = Image.new('RGB', (64, 64), color=(34, 197, 94))

    menu = pystray.Menu(
        pystray.MenuItem('Развернуть', show_window, default=True),
        pystray.MenuItem('Выход', quit_app)
    )

    tray_icon = pystray.Icon("whysovyserOverlay", image, "whysovyser Overlay", menu)

    def after_setup(icon):
        icon.visible = True
        icon.notify("Оверлей свернут в трей и работает в фоне!", "whysovyser Overlay")

    tray_icon.run(setup=after_setup)

def hide_to_tray():
    root.withdraw()
    threading.Thread(target=setup_tray, daemon=True).start()

# 6. Интерфейс Tkinter
root = tk.Tk()
root.title("whysovyser Overlay")
root.geometry("380x140")
root.resizable(False, False)
root.configure(bg="#09090b")

try:
    root.iconbitmap(get_resource_path("icon.ico"))
except:
    pass

label = tk.Label(
    root,
    text="input overlay for cs2 by whysovyser",
    fg="#22c55e",
    bg="#09090b",
    font=("Segoe UI", 11, "bold")
)
label.pack(expand=True)

status_label = tk.Label(
    root,
    text="Статус: Работает (WebSocket: 8765)",
    fg="#a1a1aa",
    bg="#09090b",
    font=("Segoe UI", 9)
)
status_label.pack(pady=(0, 15))

root.protocol("WM_DELETE_WINDOW", hide_to_tray)

if __name__ == "__main__":
    root.mainloop()
